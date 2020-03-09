import matplotlib.pyplot as plt
import pandas as pd
from pandas_flavor import register_dataframe_method, register_series_method
from gsw import density
import numpy as np
import cartopy.feature as cfeature
import cartopy.crs as ccrs
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER


@register_series_method
@register_dataframe_method
def plot_cast(df, secondary_y=False, label=None, *args, **kwargs):
    """
    Plot a CTD variable with the index in the y-axis instead of x-axis.

    """

    ax = kwargs.pop("ax", None)
    fignums = plt.get_fignums()
    if ax is None and not fignums:
        ax = plt.axes()
        fig = ax.get_figure()
        fig.set_size_inches((5.25, 6.75))
    else:
        ax = plt.gca()
        fig = plt.gcf()

    figsize = kwargs.pop("figsize", fig.get_size_inches())
    fig.set_size_inches(figsize)

    y_inverted = False
    if not getattr(ax, "y_inverted", False):
        setattr(ax, "y_inverted", True)
        y_inverted = True

    if secondary_y:
        ax = ax.twiny()

    ylabel = getattr(df.index, "name", None)

    if isinstance(df, pd.DataFrame):
        labels = label if label else df.columns
        for k, (col, series) in enumerate(df.iteritems()):
            ax.plot(series, series.index, label=labels[k])
    elif isinstance(df, pd.Series):
        label = label if label else str(df.name)
        ax.plot(df.values, df.index, label=label, *args, **kwargs)

    ax.set_ylabel(ylabel)
    ax.set_xlabel(label)

    if y_inverted and not secondary_y:
        ax.invert_yaxis()

    # Force y-axis limits to start at surface (zero)
    [ymin, ymax] = ax.get_ylim()
    ax.set_ylim([ymin, 0])

    return ax


@register_series_method
@register_dataframe_method
def plot_cast_woa(df, var, secondary_y=False, label=None, *args, **kwargs):
    """
    Plot a CTD variable with the index in the y-axis instead of x-axis.
    
    A shaded region with values (mean +/- standard deviation) of the 
    World Ocean Atlas (WOA) is also plotted. This requires to previously run
    woa_normbias.

    """

    ax = kwargs.pop("ax", None)
    fignums = plt.get_fignums()
    if ax is None and not fignums:
        ax = plt.axes()
        fig = ax.get_figure()
        fig.set_size_inches((5.25, 6.75))
    else:
        ax = plt.gca()
        fig = plt.gcf()

    figsize = kwargs.pop("figsize", fig.get_size_inches())
    fig.set_size_inches(figsize)

    y_inverted = False
    if not getattr(ax, "y_inverted", False):
        setattr(ax, "y_inverted", True)
        y_inverted = True

    if secondary_y:
        ax = ax.twiny()

    ylabel = getattr(df[var].index, "name", None)

    label = label if label else str(df[var].name)
    p = ax.plot(df[var].values, df[var].index, label=label, *args, **kwargs)

    if var == "TEMP" or var == "PSAL":
        woa_mean = df.auxiliary[var]["woa_mean"].data
        woa_std = df.auxiliary[var]["woa_std"].data
        woa_depth = df[var].index
        woa_mask = df.auxiliary[var]["woa_mean"].mask

        woa_mean = woa_mean[woa_mask == False]
        woa_std = woa_std[woa_mask == False]
        woa_depth = woa_depth[woa_mask == False]
        ax.fill_betweenx(
            woa_depth,
            woa_mean + woa_std,
            woa_mean - woa_std,
            facecolor=p[-1].get_color(),
            alpha=0.1,
        )

    # Plot bad flags if exists

    if "FLAGS" in df:
        column_index = df.columns.get_loc("TEMP")
        for index, value in df["FLAGS"].items():
            if value[column_index] == "3":
                i = df.index.get_loc(
                    index
                )  # Get position (zero-based) of the index involved
                p = ax.plot(
                    df[var].iloc[i],
                    df[var].index[i],
                    marker="o",
                    color="orange",
                    fillstyle="none",
                    markersize=4,
                    linestyle="None",
                    label="FLAG: Probably bad",
                )
            if value[column_index] == "4":
                i = df.index.get_loc(
                    index
                )  # Get position (zero-based) of the index involved
                p = ax.plot(
                    df[var].iloc[i],
                    df[var].index[i],
                    marker="o",
                    color="r",
                    fillstyle="none",
                    markersize=4,
                    linestyle="None",
                    label="FLAG: Bad",
                )
            # if value[column_index] != '1':
            #    i = df.index.get_loc(index)   # Get position (zero-based) of the index involved
            #    p = ax.plot(df[var].iloc[i], df[var].index[i], marker='o', color='r', fillstyle='none', markersize=6, label='Bad')

    ax.set_ylabel(ylabel)
    ax.set_xlabel(label)

    if y_inverted and not secondary_y:
        ax.invert_yaxis()
    return ax


@register_series_method
@register_dataframe_method
def plot_ts_diagram(df, *args, **kwargs):
    """
    Plot a T/S diagram from a DataFrame with columns TEMP and PSAL  
    
    """

    ax = kwargs.pop("ax", None)
    fignums = plt.get_fignums()
    if ax is None and not fignums:
        ax = plt.axes()
        fig = ax.get_figure()
        fig.set_size_inches((5.25, 6.75))
    else:
        ax = plt.gca()
        fig = plt.gcf()

    figsize = kwargs.pop("figsize", fig.get_size_inches())
    fig.set_size_inches(figsize)

    temp = df["TEMP"].values
    salt = df["PSAL"].values

    # Figure out boudaries (mins and maxs)
    smin = salt.min() - (0.01 * salt.min())
    smax = salt.max() + (0.01 * salt.max())
    tmin = temp.min() - (0.1 * temp.max())
    tmax = temp.max() + (0.1 * temp.max())

    # Calculate how many gridcells we need in the x and y dimensions
    xdim = int(round((smax - smin) / 0.1 + 1, 0))
    ydim = int(round((tmax - tmin) + 1, 0))

    # Create empty grid of zeros
    dens = np.zeros((ydim, xdim))

    # Create temp and salt vectors of appropiate dimensions
    ti = np.linspace(1, ydim - 1, ydim) + tmin
    si = np.linspace(1, xdim - 1, xdim) * 0.1 + smin

    # Loop to fill in grid with densities
    for j in range(0, int(ydim)):
        for i in range(0, int(xdim)):
            dens[j, i] = density.sigma0(si[i], ti[j])

    plt.rcParams["ytick.right"] = plt.rcParams["ytick.labelright"] = True

    CS = plt.contour(si, ti, dens, linestyles="dashed", colors="#bfbdbd")
    plt.clabel(CS, fontsize=8, inline=1, fmt="%0.1f")  # Label every second level

    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")

    ax.plot(salt, temp, marker="o", color="#06abd4", markersize=4)
    ax.set_xlabel("Salinity")
    h = ax.set_ylabel(u"Temperature [\u00b0C]")
    h.set_rotation(270)
    ax.yaxis.labelpad = 15

    return ax


def plot_all_casts(metadata, *args, **kwargs):

    lats = [d["lat"] for d in metadata]
    lons = [d["lon"] for d in metadata]

    offset = 1
    extent = [
        min(lons) - offset,
        max(lons) + offset,
        min(lats) - offset,
        max(lats) + offset,
    ]
    # from cartopy.io.img_tiles import Stamen
    # tiler = Stamen('terrain-background')
    # mercator = tiler.crs

    # ax = fig.add_subplot(1, 1, 1, projection=mercator)
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    # ax.add_image(tiler, 6)
    ax.stock_img()
    ax.coastlines("10m")
    gl = ax.gridlines(
        crs=ccrs.PlateCarree(),
        draw_labels=True,
        linewidth=1,
        color="gray",
        alpha=0.5,
        linestyle="--",
    )
    gl.xlabels_top = False
    gl.ylabels_left = False
    gl.xformatter = LONGITUDE_FORMATTER
    gl.yformatter = LATITUDE_FORMATTER
    gl.ylabel_style = {"color": "gray"}
    gl.xlabel_style = {"color": "gray"}
    for idx, element in enumerate(lats):
        ax.plot(
            lons[idx],
            lats[idx],
            marker="o",
            color="red",
            markersize=4,
            alpha=0.5,
            transform=ccrs.PlateCarree(),
        )

    return ax
