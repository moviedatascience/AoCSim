#Debug code
import matplotlib.pyplot as plt

def plot_region(region_vertices, map_image_path, output_path):
    x, y = zip(*region_vertices)
    map_image = plt.imread(map_image_path)
    plt.imshow(map_image)
    plt.plot(x, y, marker='o')
    plt.savefig(output_path)
    plt.close()

# Vertices data for Region 99
region_99_vertices = [
    [2599.8167701863354, 2446.7018633540374],
    [2507.254237988919, 2786.6911643099315],
    [2878.0227052217424, 2795.0929218075557],
    [3008.540400403284, 2579.4549906380525],
    [2928.962584539306, 2274.1655515962475],
    [2726.794744318182, 2327.193181818182],
    [2599.8167701863354, 2446.7018633540374]
]

# Vertices data for Region 100
region_100_vertices = [
    [3494.7282649159024, 682.997614132458],
    [3299.4907001261317, 741.7681055742767],
    [3256.3358156153818, 895.6698623836983],
    [3573.303581744656, 1050.3803196610822],
    [3640.042766245958, 1010.5709815374987],
    [3494.7282649159024, 682.997614132458]
]

# Plotting and saving the images for Region 99 and Region 100
plot_region(region_99_vertices, 'E:/AoCSim/Assets/Map_of_Verra_cleanup_notext_nowater.png', 'E:/AoCSim/Assets/region_99_plot.png')
plot_region(region_100_vertices, 'E:/AoCSim/Assets/Map_of_Verra_cleanup_notext_nowater.png', 'E:/AoCSim/Assets/region_100_plot.png')
