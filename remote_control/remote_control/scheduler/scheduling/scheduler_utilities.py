from turbo_utils.astronomy_utils import radec_to_altaz, is_twilight
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from astropy.time import Time
from sklearn.cluster import KMeans
import numpy as np

def read_targets_from_file(file_name):
    # [name, ra, dec]
    name, ra, dec = np.genfromtxt(file_name, delimiter=',', unpack=True, dtype=str)
    ra = ra.astype(float)
    dec = dec.astype(float)
    return (name, ra, dec)


def _get_even_clusters(X, n_clusters):
    # Source: https://stackoverflow.com/questions/5452576/k-means-algorithm-variation-with-equal-cluster-size
    cluster_size = int(np.ceil(len(X)/n_clusters))
    kmeans = KMeans(n_clusters, n_init='auto')
    kmeans.fit(X)
    centers = kmeans.cluster_centers_
    centers = centers.reshape(-1, 1, X.shape[-1]).repeat(
        cluster_size, 1).reshape(-1, X.shape[-1])
    distance_matrix = cdist(X, centers)
    clusters = linear_sum_assignment(distance_matrix)[1]//cluster_size
    return clusters


def separate_targets_into_clusters(targets, n):
    # Convert targets into 3D points on the unit sphere
    targets_3d = []
    for ra, dec in zip(targets[1], targets[2]):
        targets_3d.append([np.cos(np.radians(dec))*np.cos(np.radians(ra)),
                           np.cos(np.radians(dec))*np.sin(np.radians(ra)),
                           np.sin(np.radians(dec))])
    # Perform k-means clustering
    clusters = _get_even_clusters(np.array(targets_3d), n)
    # Split blocks between the telescopes.
    telescope_targets = [([],[],[]) for _ in range(n)]
    for (label, name, ra, dec) in zip(clusters, targets[0], targets[1], targets[2]):
        telescope_targets[label][0].append(name)
        telescope_targets[label][1].append(ra)
        telescope_targets[label][2].append(dec)
    telescope_targets = [(np.array(targets[0]), np.array(targets[1]), np.array(targets[2])) for targets in telescope_targets]

    return telescope_targets

def separate_targets_evenly(targets, n):
    # Split blocks between the telescopes.
    telescope_targets = [([],[],[]) for _ in range(n)]
    for i in range(len(targets[0])):
        telescope_targets[i % n][0].append(targets[0][i])
        telescope_targets[i % n][1].append(targets[1][i])
        telescope_targets[i % n][2].append(targets[2][i])
    telescope_targets = [(np.array(targets[0]), np.array(targets[1]), np.array(targets[2])) for targets in telescope_targets]

    return telescope_targets


def filter_for_visibility(targets: np.array, location: "tuple[float, float]", twilight: str = "astronomical", airmass: float = 2.):
    """ Removes targets that are not visible. Considers time of day and
        altitude/airmass
    @param targets  An array of targets to filter
    @param location A tuple of floats with the latitude and longitude of the observer in radians
    @param twilight A string with the type of twilight to use. 'civil', 'nautical', or 'astronomical'. Default is 'nautical'
    @param airmass  A float with the max airmass to look through. Default is 2.0
    @return     An array of targets with the targets that are not visible removed
    """
    if not is_twilight(location[0], location[1], twilight):
        return ([], [], [])
    
    if len(targets[0]) == 0:
        return ([], [], [])
    
    # Won't look below 10d altitude. Default airmass gives 30d
    min_altitude = max(np.pi/2 - np.arccos(1/airmass), np.radians(10))

    ra_dec = np.array(targets[1:3])

    # Get right ascension coordinates in radians
    right_ascensions = np.array(ra_dec[0], dtype=float)
    right_ascensions = np.deg2rad(right_ascensions)

    # Get declination coordinates in radians
    declinations = np.array(ra_dec[1], dtype=float)
    declinations = np.deg2rad(declinations)
    
    # Convert coordinates to altitude-azimuth
    altaz = radec_to_altaz(right_ascensions, declinations, location[0], location[1], Time(Time.now(), format='jd').value)
    
    # Remove targets with an altitude that is below the minimum
    filter = altaz[0] >= min_altitude

    targets = (targets[0][filter], targets[1][filter], targets[2][filter])

    return targets
