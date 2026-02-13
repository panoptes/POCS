"""Nightly report generation for POCS observations.

This module provides utilities to generate end-of-night reports summarizing
observations taken and reasons for non-observation (weather, errors, etc.).
"""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from panoptes.pocs.base import PanBase


class NightlyReport(PanBase):
    """Generate nightly observation reports.
    
    Creates a summary report at the end of each observing night that includes:
    - List of observations successfully taken
    - Count of exposures per field
    - Reasons for non-observation (weather, safety, errors)
    - Safety check statistics
    """

    def __init__(self, db=None, *args, **kwargs):
        """Initialize the nightly report generator.
        
        Args:
            db: Database instance to query for observation and safety data.
        """
        super().__init__(*args, **kwargs)
        self.db = db

    def generate_report(
        self,
        observed_list: Optional[Dict] = None,
        output_path: Optional[Path] = None,
        date: Optional[str] = None
    ) -> str:
        """Generate a comprehensive nightly report.
        
        Args:
            observed_list: Dictionary of observations from the scheduler's observed_list.
            output_path: Optional path to save the report to a file.
            date: Optional date string for the report. Defaults to current date.
            
        Returns:
            str: The formatted report text.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append(f"PANOPTES Nightly Observation Report - {date}")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # Observations summary
        obs_summary = self._summarize_observations(observed_list)
        report_lines.extend(obs_summary)
        report_lines.append("")
        
        # Safety summary
        safety_summary = self._summarize_safety_checks()
        report_lines.extend(safety_summary)
        report_lines.append("")
        
        report_lines.append("=" * 80)
        report_lines.append("End of Report")
        report_lines.append("=" * 80)
        
        report_text = "\n".join(report_lines)
        
        # Save to file if path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report_text)
            self.logger.info(f"Report saved to {output_path}")
        
        return report_text

    def _summarize_observations(self, observed_list: Optional[Dict] = None) -> List[str]:
        """Summarize observations taken during the night.
        
        Args:
            observed_list: Dictionary of observations from scheduler.
            
        Returns:
            List[str]: Lines of text summarizing observations.
        """
        lines = ["OBSERVATIONS SUMMARY", "-" * 80]
        
        if not observed_list or len(observed_list) == 0:
            lines.append("No observations were completed during this night.")
            return lines
        
        # Group observations by field
        field_stats = defaultdict(lambda: {"count": 0, "seq_times": []})
        
        for seq_time, observation in observed_list.items():
            field_name = observation.field.field_name
            field_stats[field_name]["count"] += 1
            field_stats[field_name]["seq_times"].append(seq_time)
        
        lines.append(f"Total observation sequences: {len(observed_list)}")
        lines.append(f"Unique fields observed: {len(field_stats)}")
        lines.append("")
        lines.append("Observations by field:")
        
        for field_name, stats in sorted(field_stats.items()):
            lines.append(f"  - {field_name}: {stats['count']} sequence(s)")
            for seq_time in stats["seq_times"]:
                obs = observed_list[seq_time]
                exp_count = getattr(obs, 'current_exp_num', 0)
                min_exp = getattr(obs, 'min_nexp', 0)
                lines.append(f"    * Started: {seq_time}, Exposures: {exp_count}/{min_exp}")
        
        return lines

    def _summarize_safety_checks(self) -> List[str]:
        """Summarize safety check results during the night.
        
        Returns:
            List[str]: Lines of text summarizing safety checks.
        """
        lines = ["SAFETY SUMMARY", "-" * 80]
        
        if self.db is None:
            lines.append("Database not available for safety summary.")
            return lines
        
        try:
            # Get the most recent safety record
            safety_record = self.db.get_current("safety")
            
            if safety_record is None:
                lines.append("No safety data available.")
                return lines
            
            # Extract the actual data from the record
            safety_data = safety_record.get("data", safety_record)
            
            lines.append("Most recent safety check:")
            
            # List each safety check and its status
            safety_checks = {
                "ac_power": "AC Power Connected",
                "is_dark": "Dark Sky",
                "good_weather": "Weather Safe",
                "free_space_root": "Root Disk Space",
                "free_space_images": "Image Disk Space"
            }
            
            all_safe = True
            for key, label in safety_checks.items():
                if key in safety_data:
                    status = "✓ PASS" if safety_data[key] else "✗ FAIL"
                    lines.append(f"  {label:.<40} {status}")
                    if not safety_data[key]:
                        all_safe = False
            
            lines.append("")
            if all_safe:
                lines.append("All safety checks passed.")
            else:
                lines.append("WARNING: Some safety checks failed.")
                lines.append("Reasons for non-observation:")
                
                failure_reasons = []
                if not safety_data.get("good_weather", True):
                    failure_reasons.append("  - Unsafe weather conditions")
                if not safety_data.get("is_dark", True):
                    failure_reasons.append("  - Not dark enough (sun above horizon)")
                if not safety_data.get("ac_power", True):
                    failure_reasons.append("  - AC power disconnected")
                if not safety_data.get("free_space_root", True):
                    failure_reasons.append("  - Insufficient disk space (root)")
                if not safety_data.get("free_space_images", True):
                    failure_reasons.append("  - Insufficient disk space (images)")
                
                lines.extend(failure_reasons)
                
        except Exception as e:
            lines.append(f"Error retrieving safety data: {e!r}")
            self.logger.warning(f"Error in safety summary: {e!r}")
        
        return lines
