import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime

# Page config
st.set_page_config(page_title="Image Selector", layout="wide")

# ========== GOOGLE SHEETS CONNECTION ==========
@st.cache_resource
def get_sheet_connection():
    scope = ['https://spreadsheets.google.com/feeds', 
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["sheet_id"]).sheet1

# ========== FUNCTIONS ==========
def get_available_images():
    """Fetch available images from Google Sheet"""
    sheet = get_sheet_connection()
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    
    # Filter for available images (in_use = False or blank)
    available = df[(df['in_use'] == False) | (df['in_use'] == '') | (df['in_use'].isna())]
    return available, df

def claim_image(image_id, task_id, project_id, sheet_df):
    """Claim an image for a worker"""
    sheet = get_sheet_connection()
    
    # Find the row for this image
    row_idx = sheet_df[sheet_df['image_id'] == image_id].index
    
    if len(row_idx) == 0:
        return False, "Image not found in database"
    
    row_idx = row_idx[0]
    sheet_row_num = row_idx + 2  # +2 for header and 1-indexing
    
    # Check if already claimed
    if sheet_df.loc[row_idx, 'in_use']:
        claimed_at = sheet_df.loc[row_idx, 'claimed_at']
        return False, f"⚠️ IMAGE ALREADY CLAIMED\\n\\nThis image (ID: {image_id}) was already claimed at {claimed_at}.\\n\\nPlease click 'Refresh Available Images' and choose a different image."
    
    # Claim the image
    timestamp = datetime.now().isoformat()
    sheet.update_cell(sheet_row_num, sheet_df.columns.get_loc('in_use') + 1, True)
    sheet.update_cell(sheet_row_num, sheet_df.columns.get_loc('claimed_at') + 1, timestamp)
    sheet.update_cell(sheet_row_num, sheet_df.columns.get_loc('task_id') + 1, task_id)
    sheet.update_cell(sheet_row_num, sheet_df.columns.get_loc('project_id') + 1, project_id)
    
    return True, "Image claimed successfully!"

# ========== MAIN APP ==========
st.title("🖼️ Image Selector")

# Get task_id and project_id from URL parameters
params = st.query_params
task_id = params.get("task_id", "UNKNOWN")
project_id = params.get("project_id", "UNKNOWN")

st.write(f"Task ID: `{task_id}`")
st.write(f"Project ID: `{project_id}`")

# ========== LOAD DATA AND SETUP FILTERS ==========
try:
    available_df, full_df = get_available_images()
    
    # ========== FILTERS ==========
    st.subheader("Filters")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Get unique domains from sheet - split comma-separated values
        all_domains = []
        for domain_str in full_df['domain'].dropna():
            if domain_str != '':
                domains = [d.strip() for d in str(domain_str).split(',')]
                all_domains.extend(domains)
        unique_domains = sorted(list(set(all_domains)))
        
        selected_domains = st.multiselect(
            "Domains:", 
            unique_domains, 
            default=None, 
            placeholder="Select domains (or leave blank for all)"
        )
    
    with col2:
        # Get unique image types from sheet - split comma-separated values
        all_types = []
        for type_str in full_df['image_type'].dropna():
            if type_str != '':
                types = [t.strip() for t in str(type_str).split(',')]
                all_types.extend(types)
        unique_types = sorted(list(set(all_types)))
        
        selected_types = st.multiselect(
            "Image Types:", 
            unique_types, 
            default=None, 
            placeholder="Select types (or leave blank for all)"
        )
    
    with col3:
        st.write("")  # Spacer
        st.write("")  # Spacer
        if st.button("🔄 Refresh"):
            st.cache_resource.clear()
            st.rerun()
    
    # ========== APPLY FILTERS ==========
    filtered_df = available_df.copy()
    
    # Filter by domain (if any selected) - support comma-separated values
    if selected_domains and len(selected_domains) > 0:
        def has_any_domain(domain_str):
            if pd.isna(domain_str) or domain_str == '':
                return False
            # Split by comma and strip whitespace
            domains = [d.strip() for d in str(domain_str).split(',')]
            # Check if any selected domain is in this image's domains
            return any(selected_domain in domains for selected_domain in selected_domains)
        
        filtered_df = filtered_df[filtered_df['domain'].apply(has_any_domain)]
    
    # Filter by image type (if any selected) - support comma-separated values
    if selected_types and len(selected_types) > 0:
        def has_any_type(type_str):
            if pd.isna(type_str) or type_str == '':
                return False
            # Split by comma and strip whitespace
            types = [t.strip() for t in str(type_str).split(',')]
            # Check if any selected type is in this image's types
            return any(selected_type in types for selected_type in selected_types)
        
        filtered_df = filtered_df[filtered_df['image_type'].apply(has_any_type)]
    
    # Show filter summary
    filter_summary = []
    if selected_domains:
        filter_summary.append(f"Domains: {', '.join(selected_domains)}")
    if selected_types:
        filter_summary.append(f"Types: {', '.join(selected_types)}")
    
    if filter_summary:
        st.info("🔍 Active filters: " + " | ".join(filter_summary))
    
    st.write(f"**{len(filtered_df)}** images match your filters (out of {len(available_df)} available, {len(full_df)} total)")
    
    if len(filtered_df) == 0:
        st.warning("No images match your filters. Try different filter options or refresh.")
    else:
        # Display images in a grid
        cols_per_row = 3
        rows = (len(filtered_df) + cols_per_row - 1) // cols_per_row
        
        for row in range(rows):
            cols = st.columns(cols_per_row)
            
            for col_idx in range(cols_per_row):
                img_idx = row * cols_per_row + col_idx
                
                if img_idx < len(filtered_df):
                    with cols[col_idx]:
                        img_data = filtered_df.iloc[img_idx]
                        
                        # Display image
                        try:
                            st.image(img_data['image_url'], use_container_width=True)
                        except:
                            st.write("🖼️ [Image Preview Not Available]")
                        
                        # Display image info
                        st.write(f"**ID:** `{img_data['image_id']}`")
                        
                        # Show domain and type if available
                        metadata_parts = []
                        if pd.notna(img_data.get('domain')) and img_data.get('domain') != '':
                            metadata_parts.append(f"📁 {img_data['domain']}")
                        if pd.notna(img_data.get('image_type')) and img_data.get('image_type') != '':
                            metadata_parts.append(f"🏷️ {img_data['image_type']}")
                        
                        if metadata_parts:
                            st.caption(" | ".join(metadata_parts))
                        
                        # Claim button
                        if st.button(f"Select This Image", key=f"claim_{img_data['image_id']}"):
                            success, message = claim_image(img_data['image_id'], task_id, project_id, full_df)
                            
                            if success:
                                st.success(message)
                                
                                # Store selected image data in session state
                                st.session_state['selected_image_id'] = img_data['image_id']
                                st.session_state['selected_image_url'] = img_data['image_url']
                                
                                # Show alert with ID and URL
                                st.components.v1.html(f"""
                                    <script>
                                    // Show alert immediately
                                    alert('✅ Image selected!\\n\\nImage ID: {img_data['image_id']}\\n\\nImage URL: {img_data['image_url']}\\n\\nCopy these values and paste them into your task before closing this window.');
                                    
                                    // Then try to send to parent window
                                    if (window.parent && window.parent !== window) {{
                                        window.parent.postMessage({{
                                            type: 'image_selected',
                                            image_id: '{img_data['image_id']}',
                                            image_url: '{img_data['image_url']}'
                                        }}, '*');
                                    }} else if (window.opener) {{
                                        window.opener.postMessage({{
                                            type: 'image_selected',
                                            image_id: '{img_data['image_id']}',
                                            image_url: '{img_data['image_url']}'
                                        }}, '*');
                                    }}
                                    </script>
                                """, height=0)
                                
                                st.balloons()
                                
                            else:
                                # Show error in popup
                                st.error(message)
                                st.components.v1.html(f"""
                                    <script>
                                    alert('⚠️ ERROR\\n\\n{message.replace("'", "\\'")}\\n\\nPlease click the Refresh button and select a different image.');
                                    </script>
                                """, height=0)

except Exception as e:
    st.error(f"Error loading images: {e}")
    st.write("Please make sure your Google Sheet is properly configured.")

# Display selected image info at bottom if available
if 'selected_image_id' in st.session_state:
    st.divider()
    st.subheader("📋 Your Selected Image")
    
    st.success("✅ Image claimed! Copy the values below and paste them into your Surge task:")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Image ID:**")
        st.code(st.session_state['selected_image_id'], language=None)
    
    with col2:
        st.write("**Image URL:**")
        st.code(st.session_state['selected_image_url'], language=None)
    
    st.info("💡 After copying, you can close this window and return to your task.")
