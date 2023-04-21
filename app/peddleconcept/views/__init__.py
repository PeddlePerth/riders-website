from .base import (
    index_view,
)

from .tours_admin import (
    schedule_editor_view,
    schedules_dashboard_view,
    schedules_dashboard_data_view,
    update_tours_data,
    venues_report_view,
    venues_report_data_view,
)

from .tours import (
    schedules_view,
    rider_schedules_view,
    tours_data_view,
)

from .riders import (
    rider_list_view,
    homepage_view,
    token_login_view_deprecated,
)

from .payroll import (
    tour_pays_view,
    tour_pays_data_view,
)