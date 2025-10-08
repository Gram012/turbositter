import numpy as np
from pathlib import Path
wk_dir = Path(__file__).parent.absolute()

def rect_tess_maker(tessfile, rafov,decfov, scale=0.97):
    rafov = np.deg2rad(rafov)*scale
    decfov = np.deg2rad(decfov)*scale
    vertical_count = int(np.ceil(np.pi / (decfov)))

    phis = []
    thetas = []

    phi = -0.5 * np.pi
    phi_step = np.pi / vertical_count
    # Loop from south to north
    for _ in range(vertical_count+1):
        # Poles
        if abs(phi) > 0.5*np.pi - 1e-8:
            horizontal_count = 1
        # Equator
        elif abs(phi) < 1e-4:
            horizontal_count = np.ceil(2*np.pi/rafov)
        # Southern hemisphere
        elif phi < 0:
            horizontal_count = np.ceil((2 * np.pi * np.cos(phi + (phi_step/2))) / (rafov))
        # Northern hemishpere
        else:
            horizontal_count = np.ceil((2 * np.pi * np.cos(phi - (phi_step/2))) / (rafov))
        theta = 0
        theta_step = 2 * np.pi / horizontal_count
        # Loop horizontally
        while theta < 2 * np.pi - 1e-8:
            phis.append(phi)
            thetas.append(theta)
            theta += theta_step
        phi += phi_step

    dec = np.rad2deg(np.array(phis))
    ra = np.rad2deg(np.array(thetas))

    with open(f'{wk_dir}/{tessfile}', "w") as fid:
        for i in range(len(ra)):
            fid.write("%d %.5f %.5f\n" % (i, ra[i], dec[i]))

def make_tess_RASA11(tessfile):
    rect_tess_maker(tessfile, 3.25, 2.07)


def find_tess_from_coords(coords, rafov, decfov, scale=0.97):
    ''' 
    Find the cooresponding tesselation for a list of (ra, dec) coordinates.
    All angles are in radians
    '''
    # Scale the fov
    rafov *= scale
    decfov *= scale

    # Find the number of fields in the vertical direction
    vertical_count = int(np.ceil(np.pi / decfov))
    # Calculate how tall each field should be
    phi_step = np.pi / vertical_count

    # Make a dictionary with the width of fields at each level
    theta_steps = np.zeros(vertical_count+1)
    id_offsets = np.zeros(vertical_count+1, dtype=int)
    current_offset = int(0)
    phi = -0.5*np.pi
    for i in range(vertical_count+1):
        # Calculate the number of fields in the horizontal direction
        horizontal_count = np.ceil((2 * np.pi * np.cos(-0.5 * np.pi + phi_step * i)) / (rafov))
        # Poles
        if abs(phi) > 0.5*np.pi - 1e-8:
            horizontal_count = 1
        # Equator
        elif abs(phi) < 1e-4:
            horizontal_count = np.ceil(2*np.pi/rafov)
        # Southern hemisphere
        elif phi < 0:
            horizontal_count = np.ceil((2 * np.pi * np.cos(phi + (phi_step/2))) / (rafov))
        # Northern hemishpere
        else:
            horizontal_count = np.ceil((2 * np.pi * np.cos(phi - (phi_step/2))) / (rafov))
        # Calculte how wide each field should be
        theta_steps[i] = 2 * np.pi / horizontal_count

        id_offsets[i] = current_offset
        current_offset += int(horizontal_count)

        phi += phi_step

    # Find field coords    
    dec = coords[:,1]
    dec += np.pi/2
    dec /= phi_step
    phi_indicies = (dec + 0.5).astype(int)

    enumerated_theta_steps = theta_steps[phi_indicies]

    ra = coords[:,0]
    ra /= enumerated_theta_steps
    theta_indicies = (ra+0.5).astype(int)

    ids = id_offsets[phi_indicies] + theta_indicies

    field_x = (theta_indicies * enumerated_theta_steps)
    field_y = (phi_indicies * phi_step - np.pi/2)
    fields = np.array([field_x, field_y])

    return ids, fields.T



def find_tess_RASA11(coords):
    return find_tess_from_coords(coords, np.deg2rad(3.25), np.deg2rad(2.07))

if __name__ == "__main__":
    make_tess_RASA11("RASA11.tess")
