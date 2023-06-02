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
    rider_tours_data_view,
    tours_data_view,
)

from .riders import (
    rider_list_view,
    rider_profile_edit_view,
    rider_profile_edit_payroll_view,
    rider_setup_invite_view,
    rider_setup_begin_view,
    rider_setup_verify_view,
    rider_setup_final_view,
    rider_token_login_migrate_view,
    rider_migrate_begin_view,
    rider_migrate_verify_view,
)

from .payroll import (
    tour_pays_view,
    tour_pays_data_view,
)

from .auth import (
    rider_login_view,
    rider_login_verify_view,
    MyLoginView,
    MyLogoutView,
)