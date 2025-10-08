"""! Simple image reduction for use on the control computer. Useful for 
processing raw fits images.
"""

from astropy.io import fits
import matplotlib.pyplot as plt
from astropy.visualization import ZScaleInterval
import numpy as np
import sep

def apply_zscale(data_array):
    zscale = ZScaleInterval()
    return zscale(data_array)

def get_sub_section(data, cutout_height=500, cutout_width=500):
    height, width = np.shape(data)
    data = data[int((height - cutout_height)/2.0): int((height + cutout_height)/2.0), int((width - cutout_width)/2.0): int((width + cutout_width)/2.0)]
    return np.ascontiguousarray(data)

def background_subtract(data):
    """! Subtracts the background from a data array
    @param data     The image data to background subtract
    @return         The hdul after being background subtracted
    """
    background = sep.Background(data, bw=64, bh=64, fw=3, fh=3)

    return data - background

def flat_field(data, flat_data):
    """! Flat fields a data array using flat_data
    @param data         The data to flat field
    @param flat_data    The flat data
    @return             Flattened data (correcting for uneven illumination across the frame)
    """
    return data / flat_data

def simple_reduce(data, flat_data, zscale_image=True):
    """! Reduces the data through a simple process (flat, background subtract, optional zscale).
    Intended for presentation or human inspection.
    @param data         The image data array
    @param flat_data    The flat data array
    @return             A reduced data array
    """
    # 1. Flatten the field to get an adjusted illumination across the field
    flattened_data = flat_field(data, flat_data)
    
    # 2. Subtract out the background
    background_subtracted_data = background_subtract(flattened_data)
    
    # 3. ZScale the image
    if zscale_image:
        reduced_data = apply_zscale(background_subtracted_data)
    else:
        reduced_data = background_subtracted_data
    
    return reduced_data

def write_fits_to_png(hdul: fits.HDUList, path, use_sub_slice=False, zcale_image=True):
    """! Writes a fits file to a png at a path
    @param hdul             The HDUL to write to a file
    @param path             The file path to write to
    @param use_sub_slice    Use the 2000x2000 centered subslice of the image
    @param zscale_image     Whether to zscale the image
    """
    primary_hdu = hdul['PRIMARY']

    data = primary_hdu.data


    width = data.shape[0] #primary_hdu.header['NAXIS1']
    height = data.shape[1] #primary_hdu.header['NAXIS2']

    if use_sub_slice:
        data = data[int(width/2.0 - 1000): int(width/2.0 + 1000), int(height/2.0 - 1000): int(height/2.0 + 1000)]
    
    if zcale_image:
        data = apply_zscale(data)
    
    plt.imsave(path, arr=data, cmap='gray', format='webp')
    plt.close()

if __name__ == "__main__":
    print("Opening Images")
    right_image = fits.open("/home/turbo/image_test_data/dewc_5_atik.fits")
    left_image = fits.open("/home/turbo/image_test_data/dewc_5_zwo.fits")

    print("Writing Images to Disk as WEBP")
    write_fits_to_png(right_image, "/var/www/html/right_image.webp")
    write_fits_to_png(left_image, "/var/www/html/left_image.webp")

    print("Conversion Complete")
