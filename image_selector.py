import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime

# Page config
st.set_page_config(page_title="Image Selector", layout="wide")

# Custom CSS
st.markdown("""
    <style>
    /* Change multiselect tag colors */
    .stMultiSelect [data-baseweb="tag"] {
        background-color: #5C7A99 !important;
    }
    
    .stMultiSelect [data-baseweb="tag"] span {
        color: white !important;
    }
    
    /* Make confirmation button green */
    div[data-testid="column"]:first-child button {
        background-color: #4CAF50 !important;
        color: white !important;
    }
    
    div[data-testid="column"]:first-child button:hover {
        background-color: #45a049 !important;
    }
    
    /* Make report bad button red/orange */
    div[data-testid="column"]:nth-child(3) button {
        background-color: #ff6b6b !important;
        color: white !important;
    }
    
    div[data-testid="column"]:nth-child(3) button:hover {
        background-color: #ee5a52 !important;
    }
    
    /* Enlarge preview image on confirmation page */
    .enlarged-image img {
        max-width: 800px !important;
        width: 100% !important;
        border: 3px solid #4CAF50;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

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
    
    # Filter for available images (in_use = False or blank, and not marked as BAD)
    available = df[
        ((df['in_use'] == False) | (df['in_use'] == '') | (df['in_use'].isna())) &
        ((df['in_use'] != 'BAD') & (df['in_use'] != 'bad'))
    ]
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
    in_use_value = sheet_df.loc[row_idx, 'in_use']
    if in_use_value == True or in_use_value == 'TRUE':
        claimed_at = sheet_df.loc[row_idx, 'claimed_at']
        return False, f"⚠️ IMAGE ALREADY CLAIMED\\n\\nThis image (ID: {image_id}) was already claimed at {claimed_at}.\\n\\nPlease click 'Refresh Available Images' and choose a different image."
    
    # Claim the image
    timestamp = datetime.now().isoformat()
    sheet.update_cell(sheet_row_num, sheet_df.columns.get_loc('in_use') + 1, True)
    sheet.update_cell(sheet_row_num, sheet_df.columns.get_loc('claimed_at') + 1, timestamp)
    sheet.update_cell(sheet_row_num, sheet_df.columns.get_loc('task_id') + 1, task_id)
    sheet.update_cell(sheet_row_num, sheet_df.columns.get_loc('project_id') + 1, project_id)
    
    return True, "Image claimed successfully!"

def mark_image_bad(image_id, task_id, project_id, sheet_df, reason):
    """Mark an image as BAD"""
    sheet = get_sheet_connection()
    
    # Find the row for this image
    row_idx = sheet_df[sheet_df['image_id'] == image_id].index
    
    if len(row_idx) == 0:
        return False, "Image not found in database"
    
    row_idx = row_idx[0]
    sheet_row_num = row_idx + 2  # +2 for header and 1-indexing
    
    # Mark as BAD
    timestamp = datetime.now().isoformat()
    sheet.update_cell(sheet_row_num, sheet_df.columns.get_loc('in_use') + 1, 'BAD')
    sheet.update_cell(sheet_row_num, sheet_df.columns.get_loc('claimed_at') + 1, timestamp)
    sheet.update_cell(sheet_row_num, sheet_df.columns.get_loc('task_id') + 1, task_id)
    sheet.update_cell(sheet_row_num, sheet_df.columns.get_loc('project_id') + 1, project_id)
    sheet.update_cell(sheet_row_num, sheet_df.columns.get_loc('report_reason') + 1, reason)
    
    return True, "Image marked as bad and removed from pool"

# ========== MAIN APP ==========
st.title("🖼️ Image Selector")

# Get task_id and project_id from URL parameters
params = st.query_params
task_id = params.get("task_id", "UNKNOWN")
project_id = params.get("project_id", "UNKNOWN")

st.write(f"Task ID: `{task_id}`")
st.write(f"Project ID: `{project_id}`")

# Initialize session state for confirmation flow
if 'preview_image' not in st.session_state:
    st.session_state['preview_image'] = None
if 'image_confirmed' not in st.session_state:
    st.session_state['image_confirmed'] = False
if 'show_report_bad' not in st.session_state:
    st.session_state['show_report_bad'] = False

# ========== CONFIRMATION PAGE (if image selected but not confirmed) ==========
if st.session_state['preview_image'] is not None and not st.session_state['image_confirmed']:
    img_data = st.session_state['preview_image']
    
    st.header("Preview Selected Image")
    
    # Show enlarged image
    st.markdown('<div class="enlarged-image">', unsafe_allow_html=True)
    try:
        st.image(img_data['image_url'], use_container_width=True)
    except:
        st.error("Could not load image preview")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Show image details
    st.write(f"**Image ID:** `{img_data['image_id']}`")
    
    # Show metadata
    metadata_parts = []
    if pd.notna(img_data.get('domain')) and img_data.get('domain') != '':
        metadata_parts.append(f"📁 Domain: {img_data['domain']}")
    if pd.notna(img_data.get('image_type')) and img_data.get('image_type') != '':
        metadata_parts.append(f"🏷️ Type: {img_data['image_type']}")
    
    if metadata_parts:
        st.info(" | ".join(metadata_parts))
    
    st.divider()
    
    # Show report bad form if requested
    if st.session_state['show_report_bad']:
        st.subheader("🚨 Report Bad Image")
        
        reason = st.text_area(
            "Why is this image inappropriate?",
            placeholder="e.g., broken link, inappropriate content, wrong category, poor quality, etc.",
            height=100
        )
        
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Submit Report", type="primary", use_container_width=True):
                if reason and len(reason.strip()) > 0:
                    _, full_df = get_available_images()
                    success, message = mark_image_bad(img_data['image_id'], task_id, project_id, full_df, reason.strip())
                    
                    if success:
                        st.success(message)
                        st.info("Thank you for reporting this image. It has been removed from the available pool.")
                        # Reset and go back to browse
                        st.session_state['preview_image'] = None
                        st.session_state['image_confirmed'] = False
                        st.session_state['show_report_bad'] = False
                        if st.button("← Back to Browse"):
                            st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Please provide a reason for reporting this image.")
        
        with col_b:
            if st.button("Cancel Report", use_container_width=True):
                st.session_state['show_report_bad'] = False
                st.rerun()
    
    else:
        # Normal confirmation view
        st.subheader("Are you sure you want to use this image?")
        st.warning("⚠️ Once confirmed, this image will be reserved for your task and removed from the available pool.")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("✅ Yes, Confirm This Image", use_container_width=True):
                # Reload data to check current status
                try:
                    _, full_df = get_available_images()
                    success, message = claim_image(img_data['image_id'], task_id, project_id, full_df)
                    
                    if success:
                        st.session_state['image_confirmed'] = True
                        st.session_state['selected_image_url'] = img_data['image_url']
                        st.rerun()
                    else:
                        # Image was claimed by someone else
                        st.error(message)
                        st.components.v1.html(f"""
                            <script>
                            alert('⚠️ ERROR\\n\\n{message.replace("'", "\\'")}');
                            </script>
                        """, height=0)
                        # Reset and go back to browse
                        st.session_state['preview_image'] = None
                        st.session_state['image_confirmed'] = False
                        if st.button("← Back to Browse"):
                            st.rerun()
                except Exception as e:
                    st.error(f"Error claiming image: {e}")
        
        with col2:
            if st.button("❌ Cancel - Choose Different Image", use_container_width=True):
                # Go back to browsing (filters preserved)
                st.session_state['preview_image'] = None
                st.session_state['image_confirmed'] = False
                st.rerun()
        
        with col3:
            if st.button("🚨 Report Bad Image", use_container_width=True):
                # Show report form
                st.session_state['show_report_bad'] = True
                st.rerun()

# ========== FINAL CONFIRMATION PAGE (image claimed successfully) ==========
elif st.session_state['image_confirmed'] and st.session_state['preview_image'] is not None:
    img_data = st.session_state['preview_image']
    
    st.success("✅ Image Successfully Claimed!")
    
    st.header("Your Selected Image")
    
    # Show enlarged image
    st.markdown('<div class="enlarged-image">', unsafe_allow_html=True)
    try:
        st.image(img_data['image_url'], use_container_width=True)
    except:
        st.error("Could not load image preview")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # Show copyable value
    st.subheader("📋 Copy This URL to Your Task")
    
    st.write("**Image URL:**")
    st.code(img_data['image_url'], language=None)
    
    # Download info
    st.divider()
    st.info("💡 **To download:** Right-click the image above and select 'Save Image As...'")
    
    # Show alert with URL
    st.components.v1.html(f"""
        <script>
        // Show alert immediately on page load
        if (!window.alertShown) {{
            alert('✅ Image selected!\\n\\nMake sure to copy the URL and paste it into your task before closing the main window.');
            window.alertShown = true;
        }}
        
        // Try to send to parent window
        if (window.parent && window.parent !== window) {{
            window.parent.postMessage({{
                type: 'image_selected',
                image_url: '{img_data['image_url']}'
            }}, '*');
        }} else if (window.opener) {{
            window.opener.postMessage({{
                type: 'image_selected',
                image_url: '{img_data['image_url']}'
            }}, '*');
        }}
        </script>
    """, height=0)
    
    st.balloons()
    
    st.divider()
    
    st.info("💡 **Important:** Keep this window open for reference. To select a different image, close this window and click the image selector link again in your Surge task.")

# ========== BROWSE/FILTER PAGE (default view) ==========
else:
    try:
        # Load data first
        available_df, full_df = get_available_images()
        
        # ========== FILTERS ==========
        st.subheader("Filters")
        
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            # Get unique domains from sheet - split by | and / separators
            all_domains = []
            for domain_str in full_df['domain'].dropna():
                if domain_str != '':
                    # First split by | to get each category path
                    categories = [c.strip() for c in str(domain_str).split('|')]
                    for category in categories:
                        # Split by / to get individual hierarchy parts
                        parts = [p.strip() for p in category.split('/')]
                        all_domains.extend(parts)
            
            # Remove duplicates and sort
            unique_domains = sorted(list(set(all_domains)))
            
            # Use session state to preserve selection
            if 'selected_domains' not in st.session_state:
                st.session_state['selected_domains'] = []
            
            selected_domains = st.multiselect(
                "Domains:", 
                unique_domains, 
                default=st.session_state['selected_domains'],
                placeholder="Select domains (or leave blank for all)",
                key='domain_filter'
            )
            
            # Update session state
            st.session_state['selected_domains'] = selected_domains
        
        with col2:
            # Get unique image types from sheet - split by | separator
            all_types = []
            for type_str in full_df['image_type'].dropna():
                if type_str != '':
                    # Split by | to get individual types
                    types = [t.strip() for t in str(type_str).split('|')]
                    all_types.extend(types)
            
            # Remove duplicates and sort
            unique_types = sorted(list(set(all_types)))
            
            # Use session state to preserve selection
            if 'selected_types' not in st.session_state:
                st.session_state['selected_types'] = []
            
            selected_types = st.multiselect(
                "Image Types:", 
                unique_types, 
                default=st.session_state['selected_types'],
                placeholder="Select types (or leave blank for all)",
                key='type_filter'
            )
            
            # Update session state
            st.session_state['selected_types'] = selected_types
        
        with col3:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("🔄 Refresh"):
                st.cache_resource.clear()
                st.session_state['preview_image'] = None
                st.session_state['image_confirmed'] = False
                # Filters will be preserved automatically
                st.rerun()
        
        # ========== APPLY FILTERS ==========
        filtered_df = available_df.copy()
        
        # Filter by domain (if any selected) - support | and / separated values
        if selected_domains and len(selected_domains) > 0:
            def has_any_domain(domain_str):
                if pd.isna(domain_str) or domain_str == '':
                    return False
                
                # Split by | to get each category path
                categories = [c.strip() for c in str(domain_str).split('|')]
                
                for category in categories:
                    # Split by / to get hierarchy parts
                    parts = [p.strip() for p in category.split('/')]
                    # Check if any selected domain matches any part
                    if any(selected_domain in parts for selected_domain in selected_domains):
                        return True
                
                return False
            
            filtered_df = filtered_df[filtered_df['domain'].apply(has_any_domain)]
        
        # Filter by image type (if any selected) - support | separated values
        if selected_types and len(selected_types) > 0:
            def has_any_type(type_str):
                if pd.isna(type_str) or type_str == '':
                    return False
                
                # Split by | and strip whitespace
                types = [t.strip() for t in str(type_str).split('|')]
                
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
                            
                            # Preview button
                            if st.button(f"👁️ Preview", key=f"preview_{img_data['image_id']}"):
                                # Store image for preview
                                st.session_state['preview_image'] = img_data.to_dict()
                                st.session_state['show_report_bad'] = False
                                st.rerun()
    
    except Exception as e:
        st.error(f"Error loading images: {e}")
        st.write("Please make sure your Google Sheet is properly configured.")
        st.write(f"Error details: {str(e)}")
