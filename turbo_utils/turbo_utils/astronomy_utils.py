from astropy.time import Time
import numpy as np


def earth_rotation_angle(jd: float):
    # IERS Technical Note No. 32

    t = jd - 2451545.0 # Get JD2000
    f = jd%1.0 # Get day number

    theta = 2*np.pi * (f + 0.7790572732640 + 0.00273781191135448 * t) #eq 14
    theta %= 2*np.pi

    return theta

   
def greenwich_mean_sidereal_time(jd: float):
    # "Expressions for IAU 2000 precession quantities" N. Capitaine1,P.T.Wallace2, and J. Chapront
    t = ((jd - 2451545.0)) / 36525.0

    gmst = earth_rotation_angle(jd)+(0.014506 + 4612.156534*t + 1.3915817*t*t - 0.00000044 *t*t*t - 0.000029956*t*t*t*t - 0.0000000368*t*t*t*t*t)/60.0/60.0*np.pi/180.0  # eq 42
    gmst%=2*np.pi

    return gmst


def local_sidereal_time(longitude: float, julian_date_UT: float):
    """ Get the local sidereal time.
    @param longitude        A float with the longitude coordinate of the observer in radians
    @param julian_date_UT   A float with time in julian universal time
    """
    universalSiderealTime = greenwich_mean_sidereal_time(julian_date_UT)
    return universalSiderealTime + longitude

def ra_to_ha(right_ascension: float, longitude: float, julian_date_UT: float = None):
    """ Convert right ascenion to hour angle. All angles are in radians
    @param right_ascension  A float with the right ascension coordinate in radians
    @param longitude        A float with the longitude coordinate of the observer in radians
    @param julian_date_UT  A float with time for the transformation in julian universal time, if ommited, the current time is used
    @return     A float with the ra coordinate translated to hour angle, in radians
    """
    if not julian_date_UT:
        julian_date_UT = Time(Time.now(), format="jd").value

    return (right_ascension - local_sidereal_time(longitude, julian_date_UT)) % (2*np.pi)


def ha_to_ra(hour_angle: float, longitude: float, julian_date_UT: float = None):
    """ Convert hour angle to right ascension. All angles are in radians
    @param hour_angle       A float with the hour angle coordinate in radians
    @param longitude        A float with the longitude coordinate of the observer in radians
    @param julian_date_UT  A float with time for the transformation in julian universal time, if ommited, the current time is used
    @return     A float with the ha coordinate translated to right ascension, in radians
    """
    if not julian_date_UT:
        julian_date_UT = Time(Time.now(), format="jd").value
    
    return (hour_angle + local_sidereal_time(longitude, julian_date_UT)) % (2*np.pi)

# All input and output angles are in radians, jd is Julian Date in UTC
def radec_to_altaz(right_ascension: float, declination: float, latitude: float, longitude: float, julian_date_UT: float = None) -> "tuple[float, float]":
    """! Converts a coordinate in right ascension and declination to altitude,
         azimuth at the given time. All angles are in radians
    @param right_ascension  A float with the right ascension coordinate in radians
    @param declination  A float with the declination coordinate in radians
    @param latitude  A float with the latitude coordinate of the observer in radians
    @param longitude  A float with the longitude coordinate of the observer in radians
    @param julian_date_UT  A float with time for the transformation in julian universal time, if ommited, the current time is used
    @return     A tuple of teo floats with the altitude and azimuth coordinates, respectively
    """
    if not julian_date_UT:
        julian_date_UT = Time(Time.now(), format="jd").value
    
    hour_angle = ra_to_ha(right_ascension, longitude, julian_date_UT)

    azimuth = np.arctan2(np.sin(hour_angle), np.cos(hour_angle)*np.sin(latitude) - np.tan(declination)*np.cos(latitude))
    altitude = np.arcsin(np.sin(latitude)*np.sin(declination) + np.cos(latitude)*np.cos(declination)*np.cos(hour_angle))
    azimuth = (azimuth - np.pi) % (2* np.pi)

    return (altitude, azimuth)


def get_sun_position(jd:float = None):
    """! Get the right ascension and declination of the sun. A time may be
         specified, otherwise the current time is used
    @param jd   A float with the julian date of the time to check. If ommited, the current time is used
    @return     A tuple of two floats with the right ascension and declination coordinates, respectively
    """
    # Default to current time
    if not jd:
        jd = Time(Time.now(), format="jd").value

    n = jd - 2451545.0 # j2000 time
    L = (4.8949504 + 0.017202792 * n) % (2*np.pi) # mean longitude
    g = (6.2400408 + 0.01720197 * n) % (2*np.pi) # mean anomaly
    l = L + 0.033423055 * np.sin(g) + 3.490659e-05 * np.sin(2*g) # ecliptic longitude
    e = 0.40908772 - 6.981317e-09 * n # obliquity of the ecliptic
    ra = np.arctan2(np.cos(e) * np.sin(l), np.cos(l))
    dec = np.arcsin(np.sin(e) * np.sin(l))
    return (ra, dec)


def is_twilight(latitude: float, longitude: float, twilight_type = "astronomical"):
    """! Checks if it currently night. Type of twilight to use may be specified
    @param latitude     A float with the latitude of the observer in radians
    @param longitude    A float with the longitude of the observer in radians
    @param twilight_type    A string with the type of twilight. One of 'civil', 'nautical', 'astronomical'
    @return     A bool. True indicates night time
    """
    sun_ra, sun_dec = get_sun_position()
    altaz = radec_to_altaz(sun_ra, sun_dec, latitude, longitude, Time(Time.now(), format="jd").value)
    
    if twilight_type == "civil":
        altitude = 0
    elif twilight_type == "nautical":
        altitude = -6
    else:
        altitude = -12

    return altaz[0] < np.radians(altitude)


def haversine(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """ Calculate the angular seperation between two points in celestial
        coordinates with angles in radians
    @param ra1  A float with the right ascension coordinate of the first point, in radians
    @param dec1 A float with the declination coordinate of the first point, in radians
    @param ra2  A float with the right ascension coordinate of the second point, in radians
    @param dec2 A float with the declination coordinate of the second point, in radians
    @return     A float with the angle between the two points in radians
    """
    return 2 * np.arcsin(np.sqrt((1 - np.cos(dec2-dec1) + np.cos(dec1) * np.cos(dec2) * (1 - np.cos(ra2-ra1))) / 2))
