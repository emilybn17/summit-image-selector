// Listen for message from Streamlit window
window.addEventListener('message', function(event) {
  console.log('Message received:', event.data);
  
  if (event.data && event.data.type === 'image_selected') {
    console.log('Processing image selection...');
    
    // Find the form fields by name attribute
    var imageIdField = document.querySelector('input[name="image_id_selected"]');
    var imageUrlField = document.querySelector('input[name="image_url_selected"]');
    
    console.log('Image ID field:', imageIdField);
    console.log('Image URL field:', imageUrlField);
    
    if (imageIdField && imageUrlField) {
      // Fill in the fields
      imageIdField.value = event.data.image_id;
      imageUrlField.value = event.data.image_url;
      
      // Trigger events so Surge recognizes the change
      imageIdField.dispatchEvent(new Event('input', { bubbles: true }));
      imageIdField.dispatchEvent(new Event('change', { bubbles: true }));
      imageUrlField.dispatchEvent(new Event('input', { bubbles: true }));
      imageUrlField.dispatchEvent(new Event('change', { bubbles: true }));
      
      console.log('Fields updated successfully');
      alert('✅ Image selected! Fields have been filled.');
    } else {
      console.error('Could not find input fields');
    }
  }
});
