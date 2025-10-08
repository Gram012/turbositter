import astropy.units as u
import matplotlib.pyplot as plt
import numpy as np
from astropy.io import fits
from astropy.visualization.wcsaxes.frame import EllipticalFrame
from astropy.wcs import WCS
from mocpy import MOC


def plot_coverage(prob_map, target_list):
    with fits.open(prob_map) as hdul:
        hdul.info()
        data = hdul[1].data
        max_order = hdul[1].header["MOCORDER"]

    uniq = data["UNIQ"]
    probdensity = data["PROBDENSITY"]

    # convert the probability density into a probability
    orders = (np.log2(uniq // 4)) // 2
    area = 4 * np.pi / np.array([MOC.n_cells(int(order)) for order in orders]) * u.sr
    prob = probdensity * area

    # now we create the mocs corresponding to different probability thresholds
    cumul_to = np.linspace(0.5, 0.9, 5)[::-1]
    colors = ["blue", "green", "yellow", "orange", "red"]
    mocs = [
        MOC.from_valued_healpix_cells(uniq, prob, max_order, cumul_to=c) for c in cumul_to
    ]

    # Plot the MOC using matplotlib
    fig = plt.figure(111, dpi=400)
    # Define a astropy WCS
    wcs = WCS({"crpix1": 1620.5,"crpix2": 810.5,"cdelt1": -0.1,"cdelt2": 0.1,"ctype1": "RA---MOL","ctype2": "DEC--MOL"})

    ax = fig.add_subplot(1, 1, 1, projection=wcs, frame_class=EllipticalFrame)
    # Call fill with a matplotlib axe and the `~astropy.wcs.WCS` wcs object.
    for moc, c, col in zip(mocs, cumul_to, colors):
        moc.fill(ax=ax, wcs=wcs, alpha=0.5, linewidth=0, fill=True, color=col)
        moc.border(ax=ax, wcs=wcs, alpha=0.5, color=col)
    ax.set_aspect(1.0)

    # Plot fields
    points = np.loadtxt(target_list, delimiter=',')
    for (_, lon, lat) in points:
        ax.text(lon, lat, ".", size=4, color="black", alpha=1, transform = ax.get_transform('world'))

    plt.grid(color="grey", linestyle="dotted")
    plt.show()

if __name__ == "__main__":
    prob_map = "bayestar.multiorder.fits,0"
    target_list = "LVC_PRELIMINARY_41904_targets.txt"
    plot_coverage(prob_map, target_list)

