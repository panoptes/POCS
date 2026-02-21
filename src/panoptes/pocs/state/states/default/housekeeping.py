from datetime import datetime
from pathlib import Path

from panoptes.pocs.utils.report import NightlyReport


def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.next_state = "sleeping"

    pocs.say("Resetting the list of observations and doing some cleanup!")

    # Generate nightly report before cleanup
    try:
        observed_list = pocs.observatory.scheduler.observed_list
        
        # Create report
        report_generator = NightlyReport(db=pocs.db)
        
        # Get reports directory from config or use default
        reports_dir = Path(
            pocs.get_config("directories.reports", default="~/reports")
        ).expanduser()
        
        # Generate filename with date
        date_str = datetime.now().strftime("%Y%m%d")
        report_path = reports_dir / f"nightly_report_{date_str}.txt"
        
        # Generate and save report
        report_text = report_generator.generate_report(
            observed_list=observed_list,
            output_path=report_path
        )
        
        pocs.logger.info(f"Nightly report generated: {report_path}")
        pocs.say(f"Generated nightly report with {len(observed_list)} observation(s)")
        
    except Exception as e:  # pragma: no cover
        pocs.logger.warning(f"Problem generating nightly report: {e!r}")

    # Cleanup existing observations
    try:
        pocs.observatory.scheduler.reset_observed_list()
    except Exception as e:  # pragma: no cover
        pocs.logger.warning(f"Problem with cleanup: {e!r}")
