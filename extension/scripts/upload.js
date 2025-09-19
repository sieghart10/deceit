class Upload {
  constructor() {
    document.addEventListener('DOMContentLoaded', () => {
      const dropZone = document.getElementById('drop-zone');
      const fileInput = document.getElementById('file-input');
      const preview = document.getElementById('preview');

      // Check for URL parameter
      const urlParams = new URLSearchParams(window.location.search);
      const imgUrl = urlParams.get('img');

      if (imgUrl) {
        preview.src = imgUrl;
        dropZone.classList.add('has-image');
      }

      // Click to upload
      dropZone.addEventListener('click', () => {
        fileInput.click();
      });

      // Handle file selection
      fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file && file.type.startsWith('image/')) {
          try {
            const imageSrc = await this.readFile(file);
            preview.src = imageSrc;
            dropZone.classList.add('has-image');
          } catch (error) {
            console.error('Error reading file:', error);
          }
        }
      });

      // Drag and drop functionality
      dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
      });

      dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
      });

      dropZone.addEventListener('drop', async (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type.startsWith('image/')) {
          try {
            const imageSrc = await this.readFile(files[0]);
            preview.src = imageSrc;
            dropZone.classList.add('has-image');
          } catch (error) {
            console.error('Error reading file:', error);
          }
        }
      });
    });
  }

  // Helper function to read files asynchronously
  readFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onload = (e) => {
        resolve(e.target.result);  // Resolve with the result (base64 string)
      };
      
      reader.onerror = (e) => {
        reject(new Error('File reading failed')); // Reject if there's an error
      };
      
      reader.readAsDataURL(file);  // Start reading the file as a data URL
    });
  }
}
