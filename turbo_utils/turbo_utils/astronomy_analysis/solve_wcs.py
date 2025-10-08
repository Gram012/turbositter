import astrometry
import sep
import numpy as np
from astropy.io import fits
import time
from turbo_utils.astronomy_analysis.image_reduction import get_sub_section

def timing_decorator(func):
    def timer_wrapper(*args, **kwargs):

        start = time.perf_counter()
        output = func(*args, **kwargs)
        end = time.perf_counter()

        print(f"{func.__name__} completed in {end - start} seconds")

        return output

    return timer_wrapper

class FailedToSolve(RuntimeError):
    pass
ASTROMETRY_CACHE_DIRECTORY = '/home/turbo/astrometry_cache/'

class PlateSolver:
    def __init__(self):
        self.solver = astrometry.Solver(
            astrometry.series_4100.index_files(
                cache_directory=ASTROMETRY_CACHE_DIRECTORY,
                scales={7, 8, 9, 10, 11, 12} # , 10, 11, 12, 13, 14, 15, 16, 17, 18, 19}
            )
            + astrometry.series_4200.index_files(
                cache_directory=ASTROMETRY_CACHE_DIRECTORY,
                scales={9, 10, 11} # , 11, 12, 13},
            )
        )
    
    @timing_decorator
    def find_sources(self, image: fits.HDUList):
        data = image['PRIMARY'].data.astype(float)
        
        subsize = 2000
        data = get_sub_section(data, subsize, subsize)
        data = np.ascontiguousarray(data)
        
        background = sep.Background(data, bw=64, bh=64, fw=3, fh=3)
        print("Background ", background.globalback)
        print("RMS ", background.globalrms)

        data_subtracted = data - background
        

        detected_sources = sep.extract(data_subtracted, 1.5, err=background.globalrms)

        # plot_sources(data_subtracted, detected_sources)

        return detected_sources

    @timing_decorator
    def solve_field(self, sources, ra_deg, dec_deg, radius_deg):
        """! Solves the field given by a list of sources to determine RA/DEC (WCS) information using astrometry.net
        """
        print(f'Telescope Location RA (deg): {ra_deg} DEC (deg): {dec_deg}')

        stars = np.stack([sources['x'], sources['y']]).T
        solution = self.solver.solve(
            stars=stars,
            size_hint = None,
            position_hint = astrometry.PositionHint(
                ra_deg=ra_deg,
                dec_deg=dec_deg,
                radius_deg=radius_deg
            ),
            solution_parameters=astrometry.SolutionParameters(
                logodds_callback=lambda logodds_list: astrometry.Action.STOP,
            ),
        )


        '''
        solution = self.solver.solve(
            stars=stars,
            size_hint = None,
            position_hint = None,
            solution_parameters=astrometry.SolutionParameters(
                logodds_callback=lambda logodds_list: astrometry.Action.STOP,
            ),
        )
        '''

        if solution.has_match():
            print(f"{solution.best_match().center_ra_deg=}")
            print(f"{solution.best_match().center_dec_deg=}")
            print(f"{solution.best_match().scale_arcsec_per_pixel=}")
            return solution
        else:
            raise FailedToSolve("Failed to solve the field!")
    
    @timing_decorator
    def solve_image(self, image: fits.HDUList):
        sources = self.find_sources(image)

        ra = image[0].header["RA"] * 15
        dec = image[0].header["DEC"]

        return self.solve_field(sources, ra, dec, 1.0)
    

if __name__ == "__main__":
    import sys

    fname = sys.argv[1]

    print(f"Solving {fname}")

    with fits.open(fname) as file:
        solver = PlateSolver()
        solution = solver.solve_image(file)
        print(f"Solution: {solution}")