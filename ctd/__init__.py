from ._version import get_versions  # noqa
from .core import CTD as _CTD  # noqa
from .plotting import (
    plot_cast,
    plot_cast_woa,
    plot_all_casts,
    plot_cast_panel,
)

from .processing import (
    bindata,
    despike,
    lp_filter,
    movingaverage,
    press_check,
    remove_above_water,
    smooth,
    split,
)

from .flagging import (
    load_cfg,
    init_flags,
    valid_datetime,
    location_at_sea,
    global_range,
    regional_range,
    gradient,
    gradient_depthconditional,
    spike,
    spike_depthconditional,
    tukey53H_norm,
    digit_roll_over,
    profile_envelop,
    woa_normbias,
    stuck_value,
    density_inversion_test,
    instrument_range,
    overall,
)

from .formatting import (
    load_mapping_P09,
    load_mapping_P01,
    to_cnv_flagged,
    to_cnv_medatlas,
    imglist_to_pdf,
    add_cruise_header,
)

from .read import (
    from_bl,
    from_btl,
    from_cnv,
    from_edf,
    from_fsi,
    rosette_summary,
    parse_csr,
    cnv_CorrectHeader,
    load_csr,
)

from .metadating import create_cdi_from_medatlas

from .extras import (
    get_distance,
    speed_test,
    csr_bounding_box_test,
    cell_thermal_mass,
    add_pxylookup_info,
)

__version__ = get_versions()["version"]
del get_versions


__all__ = [
    "bindata",
    "despike",
    "from_bl",
    "from_btl",
    "from_cnv",
    "from_edf",
    "from_fsi",
    "to_cnv_flagged",
    "to_cnv_medatlas",
    "create_cdi_from_medatlas",
    "imglist_to_pdf",
    "parse_csr",
    "cnv_CorrectHeader",
    "lp_filter",
    "movingaverage",
    "plot_cast",
    "plot_cast_woa",
    "plot_all_casts",
    "press_check",
    "remove_above_water",
    "rosette_summary",
    "smooth",
    "split",
    "add_cruise_header",
    "plot_cast_panel",
    "csr_bounding_box_test",
    "cell_thermal_mass",
    "speed_test",
    "add_pxylookup_info",
    "load_csr"
]
