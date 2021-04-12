import numpy as np
import numpy.ma as ma
from pandas_flavor import register_dataframe_method, register_series_method
import pkg_resources
import json
import warnings
import oceansdb
from oceansdb import WOA
from datetime import datetime
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon
from gsw import density

import pyxylookup
from pyxylookup import pyxylookup


warnings.simplefilter("error", UserWarning)
np.seterr(divide="ignore", invalid="ignore")  # Treatment for division by zero

"""
These quality checks mainly follow next manuals:
    - EuroGOOS "Recommendations for in-situ data Real Time Quality Control" 
    - SeaDataNet "SeaDataNet Data Quality Control Procedures"
"""


FLAG_NONE = 0
FLAG_GOOD = 1
FLAG_PROBABLY_BAD = 3
FLAG_BAD = 4
FLAG_MISSING = 9



def load_cfg(cfg=None):
    """ Load the QC configurations
    
            - The file is a dictionary composed by the variables
                to be evaluated as keys, and inside it another dictionary
                with the tests to perform as keys. example
                {'main':{
                    'valid_datetime': None,
                    },
                'temperature':{
                    'global_range':{
                        'minval': -2.5,
                        'maxval': 45,
                        },
                    },
                }
    """
    if cfg is None:
        cfg = "cfg_IEO"

    try:
        # If cfg is available in ctd, use it
        cfg = json.loads(pkg_resources.resource_string("ctd", "%s.json" % cfg))
        return cfg
    except:
        warnings.warn("This is a warning message")


@register_series_method
@register_dataframe_method
def init_flags(df):
    df.flags = ""  # Without this previous step doesn't work
    df.flags = {}
    df.flags["main"] = {}
    for varname in df.keys():
        df.flags[varname] = {}

    return


@register_series_method
@register_dataframe_method
def valid_datetime(df, metadata):
    if "time" in metadata and type(metadata["time"]) == datetime:
        flag = FLAG_GOOD
    else:
        flag = FLAG_PROBABLY_BAD
    df.flags["main"]["valid_datetime"] = flag
    return df


@register_series_method
@register_dataframe_method
def location_at_sea(df, metadata, technique):
    """
    Test if a point is located at sea or on land, based on one of these options:
        a) technique = "etopo" means that topography is extracted from ETOPO
                               and if height is positive is flagged as probably
                               bad (3)
        b) technique = "xylookup" get info from this API service
                                  https://github.com/iobis/xylookup
                                  and if on land flag as bad (4)
    """    
    if (
        ("lat" not in metadata)
        or metadata["lat"] == None
        or ("lon" not in metadata)
        or metadata["lon"] == None
    ):
        print("Missing geolocation (lat/lon)")
        flag = FLAG_MISSING
    elif (
        metadata["lat"] < -90
        or metadata["lat"] > 90
        or metadata["lon"] < -180
        or metadata["lon"] > 360
    ):
        print("Geolocation (lat/lon) not in range")
        flag = FLAG_PROBABLY_BAD
    else:
        if technique == 'etopo':
            try:
                ETOPO = oceansdb.ETOPO()
                etopo = ETOPO["topography"].extract(
                    var="height", lat=metadata["lat"], lon=metadata["lon"]
                )
                if etopo["height"] <= 0:
                    flag = FLAG_GOOD
                elif etopo["height"] > 0:
                    flag = FLAG_PROBABLY_BAD
            except:
                flag = FLAG_NONE
                print('Could not obtain depth from ETOPO grid')
        elif technique == 'xylookup':
            try:
                info_location = pyxylookup.lookup([ [metadata['lon'], metadata['lat']],
                                                     [metadata['lon'], metadata['lat']] ])
                info_location = info_location[0]
                if(info_location['shoredistance'] > 0):
                    flag = FLAG_GOOD
                else:
                    flag = FLAG_BAD
                    print('Station', metadata['name'], 'is', abs(info_location['shoredistance']/1000), 'km inland')              
            except:
                flag = FLAG_NONE
                print('Could not obtain depth from XYLOOKUP service')
        else:
            raise KeyError("Bad input argument")         
              
                
    df.flags["main"]["location_at_sea"] = flag
    return df

@register_series_method
@register_dataframe_method
def instrument_range(df, var, cfg):
    """
    This test checks that records are in the instrument range. The widest 
    range from the various models of SeaBird's CTD has been taken.
    Action: If a value fails, it should be flagged as bad data
    """

    cfg = cfg[var]["instrument_range"]
    assert cfg["minval"] < cfg["maxval"], (
        "Global Range(%s), minval (%s) must be smaller than maxval(%s)"
        % (var, cfg["minval"], cfg["maxval"])
    )

    # Default flag 0, no QC.
    flag = np.zeros(df[var].shape, dtype="i1")

    # Flag good inside acceptable range
    ind = (df[var] >= cfg["minval"]) & (df[var] <= cfg["maxval"])
    #flag[np.nonzero(ind)] = FLAG_GOOD
    flag[ind] = FLAG_GOOD

    # Flag bad outside acceptable range
    ind = (df[var] < cfg["minval"]) | (df[var] > cfg["maxval"])
    #flag[np.nonzero(ind)] = FLAG_BAD
    flag[ind] = FLAG_BAD

    # Flag as 9 any masked input value
    flag[ma.getmaskarray(df[var]) | ~np.isfinite(df[var])] = FLAG_MISSING
    df.flags[var]["instrument_range"] = flag

    return df

@register_series_method
@register_dataframe_method
def global_range(df, var, cfg):
    """
    This test applies a gross filter on observed values for temperature and 
    salinity. It needs to accommodate all of the expected extremes encountered 
    in the oceans.
    
    Action: If a value fails, it should be flagged as bad data
    """

    cfg = cfg[var]["global_range"]
    assert cfg["minval"] < cfg["maxval"], (
        "Global Range(%s), minval (%s) must be smaller than maxval(%s)"
        % (var, cfg["minval"], cfg["maxval"])
    )

    # Default flag 0, no QC.
    flag = np.zeros(df[var].shape, dtype="i1")

    # Flag good inside acceptable range
    ind = (df[var] >= cfg["minval"]) & (df[var] <= cfg["maxval"])
    #flag[np.nonzero(ind)] = FLAG_GOOD
    flag[ind] = FLAG_GOOD

    # Flag bad outside acceptable range
    ind = (df[var] < cfg["minval"]) | (df[var] > cfg["maxval"])
    #flag[np.nonzero(ind)] = FLAG_BAD
    flag[ind] = FLAG_BAD

    # Flag as 9 any masked input value
    flag[ma.getmaskarray(df[var]) | ~np.isfinite(df[var])] = FLAG_MISSING
    df.flags[var]["global_range"] = flag

    return df


@register_series_method
@register_dataframe_method
def regional_range(df, var, metadata, cfg):
    """
    This test applies only to certain regions of the world where conditions 
    can be further qualified. In this case, specific ranges for observations 
    from the Mediterranean and Red Seas further restrict what are considered 
    sensible values. 
    
    Values obtained from EuroGOOS manual.
    
    Action: Individual values that fail these ranges should be flagged as bad data. 
    """

    lat = metadata["lat"]
    lon = metadata["lon"]
    point = Point(lat, lon)

    # Default flag 0, no QC.
    flag = np.zeros(df[var].shape, dtype="i1")

    cfg = cfg[var]["regional_range"]
    for region in cfg:
        coordinates = tuple(cfg[region]["geometry"]["coordinates"])
        polygon = Polygon(*coordinates)
        if polygon.contains(point):
            print("Station inside ", region, "Evaluating regional test")
            cfg = cfg[region]

            assert cfg["minval"] < cfg["maxval"], (
                "Global Range(%s), minval (%s) must be smaller than maxval(%s)"
                % (var, cfg["minval"], cfg["maxval"])
            )

            # Flag good inside acceptable range
            ind = (df[var] >= cfg["minval"]) & (df[var] <= cfg["maxval"])
            #flag[np.nonzero(ind)] = FLAG_GOOD
            flag[ind] = FLAG_GOOD

            # Flag bad outside acceptable range
            ind = (df[var] < cfg["minval"]) | (df[var] > cfg["maxval"])
            #flag[np.nonzero(ind)] = FLAG_BAD
            flag[ind] = FLAG_BAD

            break

    # Flag as 9 any masked input value
    flag[ma.getmaskarray(df[var]) | ~np.isfinite(df[var])] = FLAG_MISSING
    df.flags[var]["regional_range"] = flag

    return df


@register_series_method
@register_dataframe_method
def gradient(df, var, cfg):
    """ Gradient QC

        This is different the mathematical gradient:
        d/dx + d/dy + d/dz,
        but as defined by GTSPP, EuroGOOS and others.
    """
    cfg = cfg[var]["gradient"]
    threshold = cfg["threshold"]

    x = df[var].values
    y = ma.masked_all_like(x)
    y[1:-1] = np.abs(x[1:-1] - (x[:-2] + x[2:]) / 2.0)

    flag = np.zeros(x.shape, dtype="i1")
    #flag[np.nonzero(y > threshold)] = FLAG_BAD
    flag[y > threshold] = FLAG_BAD
    #flag[np.nonzero(y <= threshold)] = FLAG_GOOD
    flag[y <= threshold] = FLAG_GOOD
    
    flag[ma.getmaskarray(x) | ~np.isfinite(x)] = FLAG_MISSING
    df.flags[var]["gradient"] = flag
    
    return df


@register_series_method
@register_dataframe_method
def gradient_depthconditional(df, var, cfg):
    """ Gradient Depth Condition QC
    
        It's similar to the simple gradient test, but with a threshold that is
        depth dependent.
    """
    cfg = cfg[var]["gradient_depthconditional"]

    x = df[var].values
    y = ma.masked_all_like(x)
    y[1:-1] = np.abs(x[1:-1] - (x[:-2] + x[2:]) / 2.0) 
   

    flag = np.zeros(x.shape, dtype="i1")
    
    pres = df['PRES']

    # ---- Shallow zone -----------------
    threshold = cfg["shallow_max"]
    #flag[    np.nonzero((pres <= cfg["pressure_threshold"]) & (y > threshold))] = FLAG_BAD
    #flag[(pres <= cfg["pressure_threshold"]).array & (y > threshold) & y.mask == False] = FLAG_BAD
    flag[(pres <= cfg["pressure_threshold"]) & (y.data > threshold) & (y.mask == False)] = FLAG_BAD
    #flag[    np.nonzero((pres <= cfg["pressure_threshold"]) & (y <= threshold))] = FLAG_GOOD
    #flag[(pres <= cfg["pressure_threshold"]).array & (y <= threshold) & y.mask == False] = FLAG_GOOD
    flag[(pres <= cfg["pressure_threshold"]) & (y.data <= threshold) & (y.mask == False)] = FLAG_GOOD
    # ---- Deep zone --------------------
    threshold = cfg["deep_max"]
    #flag[    np.nonzero((pres > cfg["pressure_threshold"]) & (y > threshold))] = FLAG_BAD
    #flag[(pres > cfg["pressure_threshold"]).array & (y > threshold) & y.mask == False] = FLAG_BAD
    flag[(pres > cfg["pressure_threshold"]) & (y.data > threshold) & (y.mask == False)] = FLAG_BAD
    #flag[    np.nonzero((pres > cfg["pressure_threshold"]) & (y <= threshold))] = FLAG_GOOD
    #flag[(pres > cfg["pressure_threshold"]).array & (y <= threshold) & y.mask == False] = FLAG_GOOD
    flag[(pres > cfg["pressure_threshold"]) & (y.data <= threshold) & (y.mask == False)] = FLAG_GOOD  

    flag[ma.getmaskarray(x) | ~np.isfinite(x)] = FLAG_MISSING

    df.flags[var]["gradient_depthconditional"] = flag
      
    return df


@register_series_method
@register_dataframe_method
def spike(df, var, cfg):
    cfg = cfg[var]["spike"]
    threshold = cfg["threshold"]

    x = df[var].values
    y = ma.masked_all_like(x)
    y[1:-1] = np.abs(x[1:-1] - (x[:-2] + x[2:]) / 2.0) - np.abs((x[2:] - x[:-2]) / 2.0)

    flag = np.zeros(x.shape, dtype="i1")
    #flag[np.nonzero(y > threshold)] = FLAG_BAD
    flag[y > threshold] = FLAG_BAD
    #flag[np.nonzero(y <= threshold)] = FLAG_GOOD
    flag[y <= threshold] = FLAG_GOOD
    
    flag[ma.getmaskarray(x) | ~np.isfinite(x)] = FLAG_MISSING
    
    df.flags[var]["spike"] = flag
    
    return df


@register_series_method
@register_dataframe_method
def spike_depthconditional(df, var, cfg):
    cfg = cfg[var]["spike_depthconditional"]

    x = df[var].values
    y = ma.masked_all_like(x)
    y[1:-1] = np.abs(x[1:-1] - (x[:-2] + x[2:]) / 2.0) - np.abs((x[2:] - x[:-2]) / 2.0)

    flag = np.zeros(y.shape, dtype="i1")

    pres = df['PRES']
    
    # ---- Shallow zone -----------------
    threshold = cfg["shallow_max"]
    #flag[
    #    np.nonzero((pres <= cfg["pressure_threshold"]) & (y > threshold))
    #] = FLAG_BAD
    #flag[(pres <= cfg["pressure_threshold"]).array & (y > threshold) & y.mask == False] = FLAG_BAD
    flag[(pres <= cfg["pressure_threshold"]) & (y.data > threshold) & (y.mask == False)] = FLAG_BAD    
    #flag[
    #    np.nonzero((pres <= cfg["pressure_threshold"]) & (y <= threshold))
    #] = FLAG_GOOD
    #flag[(pres <= cfg["pressure_threshold"]).array & (y <= threshold)  & y.mask == False] = FLAG_GOOD
    flag[(pres <= cfg["pressure_threshold"]) & (y.data <= threshold)  & (y.mask == False)] = FLAG_GOOD    
    # ---- Deep zone --------------------
    threshold = cfg["deep_max"]
    #flag[
    #    np.nonzero((pres > cfg["pressure_threshold"]) & (y > threshold))
    #] = FLAG_BAD
    #flag[(pres > cfg["pressure_threshold"]).array & (y > threshold) & y.mask == False] = FLAG_BAD
    flag[(pres > cfg["pressure_threshold"]) & (y.data > threshold) & (y.mask == False)] = FLAG_BAD    
    #flag[
    #    np.nonzero((pres > cfg["pressure_threshold"]) & (y <= threshold))
    #] = FLAG_GOOD
    #flag[(pres > cfg["pressure_threshold"]).array & (y <= threshold) & y.mask == False] = FLAG_GOOD
    flag[(pres > cfg["pressure_threshold"]) & (y.data <= threshold) & (y.mask == False)] = FLAG_GOOD
       
    flag[ma.getmaskarray(x) | ~np.isfinite(x)] = FLAG_MISSING
    
    df.flags[var]["spike_depthconditional"] = flag
     
    return df


@register_series_method
@register_dataframe_method
def tukey53H_norm(df, var, cfg):
    """Spike test Tukey53H() from Goring & Nikora 2002, 
       normalized by the std of the low pass

       l is the number of observations. The default l=12 is trully not
         a big number, but this test foccus on spikes, therefore, any
         variability longer than 12 is something else.
    """
    cfg = cfg[var]["tukey53H_norm"]
    threshold = cfg["threshold"]
    l = cfg["l"]

    # Tukey53H test witouh normalize
    x = df[var].values
    N = len(x)

    u1 = ma.masked_all(N)
    for n in range(N - 4):
        if x[n : n + 5].any():
            u1[n + 2] = ma.median(x[n : n + 5])

    u2 = ma.masked_all(N)
    for n in range(N - 2):
        if u1[n : n + 3].any():
            u2[n + 1] = ma.median(u1[n : n + 3])

    u3 = ma.masked_all(N)
    u3[1:-1] = 0.25 * (u2[:-2] + 2 * u2[1:-1] + u2[2:])

    Delta = ma.absolute(x - u3)

    # Normalize
    w = np.hamming(l)
    sigma = (np.convolve(x, w, mode="same") / w.sum()).std()
    y = Delta / sigma

    # Flag
    flag = np.zeros(x.shape, dtype="i1")
    #flag[np.nonzero(y > threshold)] = FLAG_BAD
    flag[y > threshold] = FLAG_BAD
    #flag[np.nonzero(y <= threshold)] = FLAG_GOOD
    flag[y <= threshold] = FLAG_GOOD
    
    flag[ma.getmaskarray(x) | ~np.isfinite(x)] = FLAG_MISSING
    
    df.flags[var]["tukey53H_norm"] = flag
    
    return df


@register_series_method
@register_dataframe_method
def digit_roll_over(df, var, cfg):
    """
    Modified to only mask one value and not adjacent values

    """
    threshold = cfg[var]["digit_roll_over"]

    x = df[var].values
    y = ma.masked_all(x.shape, dtype=x.dtype)
    y[1:] = ma.diff(x)

    flag = np.zeros(y.shape, dtype="i1")   
    flag[y > threshold] = FLAG_BAD
    #flag[ma.absolute(y) <= threshold] = FLAG_GOOD

    flag[ma.getmaskarray(x) | ~np.isfinite(x)] = FLAG_MISSING
    
    df.flags[var]["digit_roll_over"] = flag
    
    return df


@register_series_method
@register_dataframe_method
def profile_envelop(df, var, cfg):
    """    
        Probably not the best way to do this, but works for now.
    """
    cfg = cfg[var]["profile_envelop"]

    #z = df.index.values
    z = df['PRES']
    x = df[var].values

    flag = np.zeros(z.shape, dtype="i1")

    for layer in cfg:
        #ind = np.nonzero(eval("(z %s) & (z %s)" % (layer[0], layer[1])))[0]
        ind = np.nonzero(eval("(z.array %s) & (z.array %s)" % (layer[0], layer[1])))[0]
        f = eval("(x[ind] > %s) & (x[ind] < %s)" % (layer[2], layer[3]))

        flag[ind[f == True]] = FLAG_GOOD
        flag[ind[f == False]] = FLAG_BAD

    flag[ma.getmaskarray(x) | ~np.isfinite(x)] = FLAG_MISSING
    
    df.flags[var]["profile_envelop"] = flag
    
    return df


@register_series_method
@register_dataframe_method
def woa_normbias(df, varname, metadata, cfg):

    lat = metadata["lat"]
    lon = metadata["lon"]
    time = metadata["time"]

    if lat is None or lon is None or time is None:
        assert False, "I'm not ready for that. Position or time cast not found."

    #pres = df.index.values
    pres = df['PRES']
    x = df[varname].values

    doy = int(time.strftime("%j"))

    db = WOA()
    
    if varname == 'TE01' or varname == 'TE02':
        varname_woa = 'TEMP'
    else:
        varname_woa = varname

    woa = db[varname_woa].extract(
        var=["mean", "standard_deviation", "number_of_observations"],
        doy=doy,
        depth=pres,
        lat=lat,
        lon=lon,
    )

    woa_normbias = (x - woa["mean"]) / woa["standard_deviation"]
    normbias_abs = np.absolute(woa_normbias)

    # 3 is the possible minimum to estimate the std, but I shold use higher.
    try:
        min_samples = cfg[varname]["woa_normbias"]["min_samples"]
    except:
        min_samples = 3

    threshold = cfg[varname]["woa_normbias"]["threshold"]
    assert (np.size(threshold) == 1) and (threshold is not None)

    flag = np.zeros(x.shape, dtype="i1")
    
    #flag[
    #    np.nonzero(
    #        (woa["number_of_observations"] >= min_samples) & (normbias_abs <= threshold)
    #    )
    #] = FLAG_GOOD
    flag[(woa["number_of_observations"] >= min_samples) & (normbias_abs <= threshold)] = FLAG_GOOD    
    #flag[
    #    np.nonzero(
    #        (woa["number_of_observations"] >= min_samples) & (normbias_abs > threshold)
    #    )
    #] = FLAG_BAD
    flag[(woa["number_of_observations"] >= min_samples) & (normbias_abs > threshold)] = FLAG_BAD

    flag[ma.getmaskarray(x) | ~np.isfinite(x)] = FLAG_MISSING
    
    df.flags[varname]["woa_normbias"] = flag

    # Save auxiliary data into DataFrame
    if not hasattr(df, "auxiliary"):
        df.auxiliary = ""
        df.auxiliary = {}
    df.auxiliary[varname] = {
        "woa_mean": woa["mean"],
        "woa_std": woa["standard_deviation"],
        "woa_nsamples": woa["number_of_observations"],
        "woa_bias": x - woa["mean"],
        "woa_normbias": woa_normbias,
    }

    return df


@register_series_method
@register_dataframe_method
def stuck_value(df, var):
    """
    Looks for ALL measurements in a profile being identical.
    
    Action: If this occurs, all of the values of the
    affected variable should be flagged as bad data.     
    """

    x = df[var].values

    flag = np.zeros(x.shape, dtype="i1")
    if len(np.unique(x)) == 1:
        flag[:] = FLAG_BAD
    else:
        flag[:] = FLAG_GOOD
        
    flag[ma.getmaskarray(x) | ~np.isfinite(x)] = FLAG_MISSING    

    df.flags[var]["stuck_value"] = flag
    return df


@register_series_method
@register_dataframe_method
def density_inversion_test(df):
    """
    With few exceptions, potential water density σθ will increase with increasing 
    pressure. When vertical profile data are obtained, this test is used to 
    flag as failed T, C, and S observations, which yield densities that do not 
    sufficiently increase with pressure   
    """

    threshold = 0.03

    if "TEMP" and "PSAL" in df.columns:
        t = df["TEMP"].values
        s = df["PSAL"].values

        dens = density.sigma0(s, t)

        y = ma.masked_all(t.shape, dtype=t.dtype)
        y[1:] = ma.diff(dens)

        flag = np.zeros(y.shape, dtype="i1")       
        flag[y < -threshold] = FLAG_PROBABLY_BAD
        flag[y >= -threshold] = FLAG_GOOD
        df.flags["TEMP"]["density_inversion_test"] = flag
        df.flags["PSAL"]["density_inversion_test"] = flag
        

    return df


@register_series_method
@register_dataframe_method
def overall(df, varname):
    flags = df.flags[varname]
    criteria = list(flags.keys())
    output = np.asanyarray(flags[criteria[0]])
    for c in criteria[1:]:
        assert len(flags[c]) == len(output)
        output = np.max([output, flags[c]], axis=0)
    df.flags[varname]["overall"] = output
    return df
