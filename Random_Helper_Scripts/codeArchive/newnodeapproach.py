from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
import numpy as np

# Load the image
image_path = 'E:/AoCSim/Assets/Map_of_Verra_cleanup_notext_nowater.png'
img = Image.open(image_path)
width, height = img.size

# Convert image to numpy array for processing
img_array = np.array(img)

# Parameters
num_regions = 100
grid_size = int(np.sqrt(num_regions))  # Assuming a square grid for simplicity

# Initialize an image for output
output_img = Image.new("RGBA", img.size)
draw = ImageDraw.Draw(output_img)
output_img.paste(img, (0, 0))

# Create a grid overlay and draw borders
for x in range(0, width, width // grid_size):
    for y in range(0, height, height // grid_size):
        # Determine if the grid cell falls predominantly on land
        cell = img_array[y:y + height // grid_size, x:x + width // grid_size]
        if np.any(cell[:, :, 3] != 0):  # Check alpha channel for non-transparency
            # Draw border for this region
            draw.rectangle([x, y, x + width // grid_size, y + height // grid_size], outline="black", width=1)

# Visualization
plt.imshow(output_img)
plt.axis('off')
plt.show()
