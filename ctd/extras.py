import matplotlib.pyplot as plt
import numpy as np
import numpy.ma as ma
from pandas import Series
from math import sin, cos, sqrt, atan2, radians
from flask import flash
from pyxylookup import pyxylookup
flash_messages = True

def _extrap1d(interpolator):
    """
    http://stackoverflow.com/questions/2745329/
    How to make scipy.interpolate return an extrapolated result beyond the
    input range.

    """
    xs, ys = interpolator.x, interpolator.y

    def pointwise(x):
        if x < xs[0]:
            return ys[0] + (x - xs[0]) * (ys[1] - ys[0]) / (xs[1] - xs[0])
        elif x > xs[-1]:
            return ys[-1] + (x - xs[-1]) * (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
        else:
            return interpolator(x)

    def ufunclike(xs):
        return np.array(list(map(pointwise, np.array(xs))))

    return ufunclike


def get_maxdepth(self):
    valid_last_depth = self.apply(Series.notnull).values.T
    return np.float_(self.index.values * valid_last_depth).max(axis=1)


def extrap_sec(data, dist, depth, w1=1.0, w2=0):
    """
    Extrapolates `data` to zones where the shallow stations are shadowed by
    the deep stations.  The shadow region usually cannot be extrapolates via
    linear interpolation.

    The extrapolation is applied using the gradients of the `data` at a certain
    level.

    Parameters
    ----------
    data : array_like
          Data to be extrapolated
    dist : array_like
           Stations distance
    fd : float
         Decay factor [0-1]


    Returns
    -------
    Sec_extrap : array_like
                 Extrapolated variable

    """
    from scipy.interpolate import interp1d

    new_data1 = []
    for row in data:
        mask = ~np.isnan(row)
        if mask.any():
            y = row[mask]
            if y.size == 1:
                row = np.repeat(y, len(mask))
            else:
                x = dist[mask]
                f_i = interp1d(x, y)
                f_x = _extrap1d(f_i)
                row = f_x(dist)
        new_data1.append(row)

    new_data2 = []
    for col in data.T:
        mask = ~np.isnan(col)
        if mask.any():
            y = col[mask]
            if y.size == 1:
                col = np.repeat(y, len(mask))
            else:
                z = depth[mask]
                f_i = interp1d(z, y)
                f_z = _extrap1d(f_i)
                col = f_z(depth)
        new_data2.append(col)

    new_data = np.array(new_data1) * w1 + np.array(new_data2).T * w2
    return new_data


def gen_topomask(h, lon, lat, dx=1.0, kind="linear", plot=False):
    """
    Generates a topography mask from an oceanographic transect taking the
    deepest CTD scan as the depth of each station.

    Inputs
    ------
    h : array
        Pressure of the deepest CTD scan for each station [dbar].
    lons : array
           Longitude of each station [decimal degrees east].
    lat : Latitude of each station. [decimal degrees north].
    dx : float
         Horizontal resolution of the output arrays [km].
    kind : string, optional
           Type of the interpolation to be performed.
           See scipy.interpolate.interp1d documentation for details.
    plot : bool
           Whether to plot mask for visualization.

    Outputs
    -------
    xm : array
         Horizontal distances [km].
    hm : array
         Local depth [m].

    Author
    ------
    André Palóczy Filho (paloczy@gmail.com) --  October/2012

    """

    import gsw
    from scipy.interpolate import interp1d

    h, lon, lat = list(map(np.asanyarray, (h, lon, lat)))
    # Distance in km.
    x = np.append(0, np.cumsum(gsw.distance(lon, lat)[0] / 1e3))
    h = -gsw.z_from_p(h, lat.mean())
    Ih = interp1d(x, h, kind=kind, bounds_error=False, fill_value=h[-1])
    xm = np.arange(0, x.max() + dx, dx)
    hm = Ih(xm)

    return xm, hm


def plot_section(self, reverse=False, filled=False, **kw):
    import gsw

    lon, lat, data = list(map(np.asanyarray, (self.lon, self.lat, self.values)))
    data = ma.masked_invalid(data)
    h = self.get_maxdepth()
    if reverse:
        lon = lon[::-1]
        lat = lat[::-1]
        data = data.T[::-1].T
        h = h[::-1]
    lon, lat = map(np.atleast_2d, (lon, lat))
    x = np.append(0, np.cumsum(gsw.distance(lon, lat)[0] / 1e3))
    z = self.index.values.astype(float)

    if filled:  # CAVEAT: this method cause discontinuities.
        data = data.filled(fill_value=np.nan)
        data = extrap_sec(data, x, z, w1=0.97, w2=0.03)

    # Contour key words.
    extend = kw.pop("extend", "both")
    fontsize = kw.pop("fontsize", 12)
    labelsize = kw.pop("labelsize", 11)
    cmap = kw.pop("cmap", plt.cm.rainbow)
    levels = kw.pop(
        "levels", np.arange(np.floor(data.min()), np.ceil(data.max()) + 0.5, 0.5),
    )

    # Colorbar key words.
    pad = kw.pop("pad", 0.04)
    aspect = kw.pop("aspect", 40)
    shrink = kw.pop("shrink", 0.9)
    fraction = kw.pop("fraction", 0.05)

    # Topography mask key words.
    dx = kw.pop("dx", 1.0)
    kind = kw.pop("kind", "linear")
    linewidth = kw.pop("linewidth", 1.5)

    # Station symbols key words.
    station_marker = kw.pop("station_marker", None)
    color = kw.pop("color", "k")
    offset = kw.pop("offset", -5)
    alpha = kw.pop("alpha", 0.5)

    # Figure.
    figsize = kw.pop("figsize", (12, 6))
    fig, ax = plt.subplots(figsize=figsize)
    xm, hm = gen_topomask(h, lon, lat, dx=dx, kind=kind)
    ax.plot(xm, hm, color="black", linewidth=linewidth, zorder=3)
    ax.fill_between(xm, hm, y2=hm.max(), color="0.9", zorder=3)

    if station_marker:
        ax.plot(
            x,
            [offset] * len(h),
            color=color,
            marker=station_marker,
            alpha=alpha,
            zorder=5,
        )
    ax.set_xlabel("Cross-shore distance [km]", fontsize=fontsize)
    ax.set_ylabel("Depth [m]", fontsize=fontsize)
    ax.set_ylim(offset, hm.max())
    ax.invert_yaxis()

    ax.xaxis.set_ticks_position("top")
    ax.xaxis.set_label_position("top")
    ax.yaxis.set_ticks_position("left")
    ax.yaxis.set_label_position("left")
    ax.xaxis.set_tick_params(tickdir="out", labelsize=labelsize, pad=1)
    ax.yaxis.set_tick_params(tickdir="out", labelsize=labelsize, pad=1)

    # Color version.
    cs = ax.contourf(
        x, z, data, cmap=cmap, levels=levels, alpha=1.0, extend=extend, zorder=2,
    )  # manual=True
    # Colorbar.
    cb = fig.colorbar(
        mappable=cs,
        ax=ax,
        orientation="vertical",
        aspect=aspect,
        shrink=shrink,
        fraction=fraction,
        pad=pad,
    )
    return fig, ax, cb


def cell_thermal_mass(temperature, conductivity):
    """
    Sample interval is measured in seconds.
    Temperature in degrees.
    CTM is calculated in S/m.

    """

    alpha = 0.03  # Thermal anomaly amplitude.
    beta = 1.0 / 7  # Thermal anomaly time constant (1/beta).

    sample_interval = 1 / 15.0
    a = 2 * alpha / (sample_interval * beta + 2)
    b = 1 - (2 * a / alpha)
    #dCodT = 0.1 * (1 + 0.006 * [temperature - 20])
    #dT = np.diff(temperature)
    # Modified by POT to create same lengths arrays
    dCodT = 0.1 * (1 + 0.006 * (temperature - 20))
    dT = np.diff(temperature, prepend=temperature[0])
    ctm = -1.0 * b * conductivity + a * (dCodT) * dT  # [S/m]
    return ctm


def mixed_layer_depth(CT, method="half degree"):
    if method == "half degree":
        mask = CT[0] - CT < 0.5
    else:
        mask = np.zeros_like(CT)
    return Series(mask, index=CT.index, name="MLD")


def barrier_layer_thickness(SA, CT):
    """
    Compute the thickness of water separating the mixed surface layer from the
    thermocline.  A more precise definition would be the difference between
    mixed layer depth (MLD) calculated from temperature minus the mixed layer
    depth calculated using density.

    """
    import gsw

    sigma_theta = gsw.sigma0(SA, CT)
    mask = mixed_layer_depth(CT)
    mld = np.where(mask)[0][-1]
    sig_surface = sigma_theta[0]
    sig_bottom_mld = gsw.sigma0(SA[0], CT[mld])
    d_sig_t = sig_surface - sig_bottom_mld
    d_sig = sigma_theta - sig_bottom_mld
    mask = d_sig < d_sig_t  # Barrier layer.
    return Series(mask, index=SA.index, name="BLT")


def get_distance(lat1, lon1, lat2, lon2):

    # approximate radius of earth in km
    R = 6373.0

    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = R * c

    return distance


def speed_test(metadata, cfg):
    """Compute speed between stations.
        
        A too short time between stations may indicate a problem in
        geoposition. Typically, a research vessel does not exceed 15 knots. 
    """
    
    if flash_messages:
        flash('Test: speed of vessel', "success")
    
    cfg = cfg["main"]["max_speed"]

    positions = sorted(zip([d["time"] for d in metadata],
                           [d["lat"] for d in metadata],
                           [d["lon"] for d in metadata],
                           [d["name"] for d in metadata]))
    times = [x[0] for x in positions]
    lats = [x[1] for x in positions]
    lons = [x[2] for x in positions]
    stations = [x[3] for x in positions]
  
    if len(times) != len(set(times)):
        test_ok = False
        print('Some stations were done at exactly the same time! Check sampling times in files')
        if flash_messages:
            flash('Some stations were done at exactly the same time! Check sampling times in files', "danger")
        
    for idx in range(len(times) - 1):
        distance = get_distance(lats[idx], lons[idx], lats[idx + 1], lons[idx + 1])
        delta_time = (times[idx + 1] - times[idx]).total_seconds()
        speed = (distance / 1.852) / (delta_time / 3600) 
        if speed > cfg:
            print(
                "WARNING: It seems that vessel navigated too fast between file "
                + stations[idx]
                + " and "
                + stations[idx + 1]
            )
            print("         Please, check positions and time!")
            if flash_messages:
                flash('Vessel navigated too fast between file '
                    + stations[idx]
                    + ' and '
                    + stations[idx + 1]
                    + '. Please, check positions and time!', "warning")
        elif speed == 0:
            print(
                "WARNING: Same position of files "
                + stations[idx]
                + " and "
                + stations[idx + 1]
            )
            print("         Please, check positions!")
            if flash_messages:
                flash('Same position of file '
                    + stations[idx]
                    + ' and '
                    + stations[idx + 1]
                    + '. Please, check geoposition in files!', "danger")            
            
    return


def csr_bounding_box_test(metadata, csr):
    """ Check if CTDs stations are inside the bounding box of the CSR
        
       Input: - metadata info as obtained with 'from_cnv'
              - csr info as obtained from 'load_csr'
    """ 

    if flash_messages:
        flash('Test: CTDs inside CSR bounding box', "success")

    if csr['cruise_location'] is not None:
              
        min_lat = min([d['lat'] for d in metadata])
        max_lat = max([d['lat'] for d in metadata])
        min_lon = min([d['lon'] for d in metadata])
        max_lon = max([d['lon'] for d in metadata])
        if min_lat < float(csr['cruise_location'][0]) or \
           max_lat > float(csr['cruise_location'][1]) or \
           min_lon < float(csr['cruise_location'][2]) or \
           max_lon > float(csr['cruise_location'][3]):  
            print("WARNING: Coordinates are out the bounding box of the campaign (CSR file). \n"
                  "CTDs bounding box is [", min_lat, " ", max_lat, " ", min_lon, " ", max_lon, "]\n"
                  "CSR  bounding box is [", float(csr['cruise_location'][0]), " ", float(csr['cruise_location'][1]), " ", float(csr['cruise_location'][2]), " ", float(csr['cruise_location'][3]), "]\n"
                  "If the problem is in the bounding box of the CSR, inform to your National Oceanographic Data Center")
            if flash_messages:
                flash('Coordinates are out the bounding box of the campaign (CSR file). \n'
                      + 'CTDs bounding box is [' + '{:.2f}'.format(min_lat) + ' ' + '{:.2f}'.format(max_lat) + ' ' + '{:.2f}'.format(min_lon) + ' ' + '{:.2f}'.format(max_lon) + ']\n'
                      + 'CSR  bounding box is [' + '{:.2f}'.format(float(csr['cruise_location'][0])) + ' ' + '{:.2f}'.format(float(csr['cruise_location'][1])) + ' ' + '{:.2f}'.format(float(csr['cruise_location'][2])) + ' ' + '{:.2f}'.format(float(csr['cruise_location'][3])) + '].\n'
                      + 'If the problem is in the bounding box of the CSR, inform to your National Oceanographic Data Center', "danger")
    else:
        print("WARNING: not bounding box was found in CSR file")
        if flash_messages:
            flash('Not bounding box was found in CSR file.', "danger")
    
    return            

      


"""
    Add pxylookup info to metadata
"""
def add_pxylookup_info(metadata):
    """ Add pxylookup info to metadata
        Input: metadata as obtained with cast = from_cnv(fname)
                                         metadata = cast._metadata
        Output: metadata with following variables added:
            - shoredistance
            - sstemperature
            - sssalinity
            - bathymetry
    """
    locations = []
    if len(metadata)==1:
        locations.append([metadata[0]['lon'], metadata[0]['lat']])
        locations.append([metadata[0]['lon'], metadata[0]['lat']])
    else:    
        for location in metadata:
            locations.append([location['lon'], location['lat']])
            
    info_locations = pyxylookup.lookup(locations)
    
    for idx, station in enumerate(metadata):
        if len(metadata)==1:
            info_locations = info_locations[0]
            shoredistance = info_locations['shoredistance']
            try:
                sstemperature = info_locations['grids']['sstemperature']
            except:
                sstemperature = None
            try:
                sssalinity = info_locations['grids']['sssalinity']
            except:
                sssalinity = None        
            try:
                bathymetry = info_locations['grids']['bathymetry']
            except:
                bathymetry = None        
        else:       
            shoredistance = info_locations[idx]['shoredistance']
            try:
                sstemperature = info_locations[idx]['grids']['sstemperature']
            except:
                sstemperature = None
            try:
                sssalinity = info_locations[idx]['grids']['sssalinity']
            except:
                sssalinity = None        
            try:
                bathymetry = info_locations[idx]['grids']['bathymetry']
            except:
                bathymetry = None                       
        adict={'shoredistance': shoredistance,
               'sstemperature': sstemperature,           
               'sssalinity': sssalinity,
               'bathymetry': bathymetry           
               }
        metadata[idx].update(adict.copy())
        
    return    
    
    
    