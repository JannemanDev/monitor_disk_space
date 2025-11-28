#!/usr/bin/env python3
"""
Disk Space Monitor with Pushover Notifications

Checks disk space once and sends Pushover notifications when disk space
falls below the configured threshold. Designed to be run via cron job.
"""

import os
import shutil
import re
import json
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import requests


class DiskSpaceMonitor:
    """Monitor disk space and send Pushover notifications."""

    def __init__(self, config: Dict, settings_file_path: Optional[str] = None):
        """
        Initialize the monitor with configuration.

        Args:
            config: Dictionary containing:
                - pushover_token: Pushover API token
                - pushover_user: Pushover user key
                - max_push_notifications_per_day: (Optional) Maximum notifications per day
                - data_folder: (Optional) Path to folder for logs, graphs, and tracking files.
                  Can be relative (to settings file directory) or absolute. Default: "data"
                - drives: List of drive configurations, each with:
                  * path: Drive path (e.g., "C:", "/")
                  * minimum_disk_space: Minimum disk space threshold (e.g., "10GB", "500MB")
            settings_file_path: Path to settings file (used for tracking file location)
        """
        self.pushover_token = config.get("pushover_token")
        self.pushover_user = config.get("pushover_user")
        self.max_push_notifications_per_day = config.get(
            "max_push_notifications_per_day"
        )

        # Parse drives configuration
        drives_config = config.get("drives", [])
        self.drives = self._parse_drives_config(drives_config)

        # Set up data directory for logs, graphs, and tracking files
        if settings_file_path:
            base_dir = Path(settings_file_path).parent
        else:
            base_dir = Path.cwd()

        # Get data folder path from config (default: "data")
        data_folder = config.get("data_folder", "data")

        # Create data directory if it doesn't exist
        # Handle both relative and absolute paths
        if Path(data_folder).is_absolute():
            self.data_dir = Path(data_folder)
        else:
            self.data_dir = base_dir / data_folder
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.tracking_file = self.data_dir / ".notification_tracking.json"

        if not self.pushover_token or not self.pushover_user:
            raise ValueError("Pushover token and user key are required")

        if not self.drives:
            raise ValueError("At least one drive must be specified")

    def _parse_drives_config(self, drives_config: list) -> list:
        """
        Parse drives configuration into a list of drive dictionaries.

        Each drive must be an object with 'path' and 'minimum_disk_space' fields.

        Args:
            drives_config: Drives configuration from settings

        Returns:
            List of dictionaries with 'path' and 'minimum_bytes' keys
        """
        drives = []

        for drive_config in drives_config:
            if not isinstance(drive_config, dict):
                raise ValueError(
                    f"Invalid drive configuration: {drive_config}. "
                    f"Each drive must be an object with 'path' and 'minimum_disk_space' fields."
                )

            path = drive_config.get("path")
            if not path:
                raise ValueError("Drive configuration must include 'path' field")

            minimum_str = drive_config.get("minimum_disk_space")
            if not minimum_str:
                raise ValueError(
                    f"Drive '{path}' must specify 'minimum_disk_space' threshold"
                )

            minimum_bytes = self._parse_size(minimum_str)

            drives.append({"path": path, "minimum_bytes": minimum_bytes})

        return drives

    def _parse_size(self, size_str: str) -> int:
        """
        Parse human-friendly size string to bytes.

        Supports: B, KB, MB, GB, TB (case-insensitive)

        Args:
            size_str: Size string (e.g., "10GB", "500MB", "1TB")

        Returns:
            Size in bytes
        """
        size_str = size_str.strip().upper()

        # Match number and unit
        match = re.match(r"^(\d+(?:\.\d+)?)\s*([KMGT]?B?)$", size_str)
        if not match:
            raise ValueError(
                f"Invalid size format: {size_str}. Use format like '10GB', '500MB'"
            )

        value = float(match.group(1))
        unit = match.group(2)

        # Handle 'B' suffix
        if unit == "B" or unit == "":
            multiplier = 1
        elif unit == "KB":
            multiplier = 1024
        elif unit == "MB":
            multiplier = 1024**2
        elif unit == "GB":
            multiplier = 1024**3
        elif unit == "TB":
            multiplier = 1024**4
        else:
            raise ValueError(f"Unsupported unit: {unit}")

        return int(value * multiplier)

    def get_disk_space(self, drive: str) -> Optional[Dict]:
        """
        Get disk space information for a drive.

        Args:
            drive: Drive path (e.g., "C:", "/")

        Returns:
            Dictionary with 'total', 'used', 'free' in bytes, or None if error
        """
        try:
            # Normalize drive path
            if os.name == "nt":  # Windows
                if not drive.endswith("\\") and not drive.endswith("/"):
                    drive = drive + "\\"
            else:  # Unix-like
                if not drive.endswith("/"):
                    drive = drive + "/"

            stat = shutil.disk_usage(drive)
            return {
                "total": stat.total,
                "used": stat.used,
                "free": stat.free,
                "path": drive,
            }
        except Exception as e:
            print(f"Error checking disk space for {drive}: {e}")
            return None

    def format_bytes(self, bytes: int) -> str:
        """Format bytes to human-readable string."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes < 1024.0:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.2f} PB"

    def format_bytes_multiple_units(self, bytes: int) -> str:
        """
        Format bytes to human-readable string with multiple units.
        Example: "1 TB 54 GB 239 MB"

        Args:
            bytes: Size in bytes

        Returns:
            Formatted string with all non-zero units
        """
        if bytes == 0:
            return "0 B"

        units = [
            ("TB", 1024**4),
            ("GB", 1024**3),
            ("MB", 1024**2),
            ("KB", 1024),
            ("B", 1),
        ]

        parts = []
        remaining = bytes

        for unit_name, unit_size in units:
            if remaining >= unit_size:
                value = remaining // unit_size
                parts.append(f"{value} {unit_name}")
                remaining = remaining % unit_size

        return " ".join(parts) if parts else "0 B"

    def _get_log_filename(self, drive_path: str) -> Path:
        """
        Get a safe log filename for a drive path.

        Args:
            drive_path: Drive path (e.g., "C:", "/")

        Returns:
            Path to the log file
        """
        # Create a safe filename from the drive path
        # Remove trailing slashes/backslashes and special characters
        safe_name = drive_path.rstrip("\\/").replace("\\", "_").replace("/", "_")

        # Handle root path
        if safe_name == "" or safe_name == "_":
            safe_name = "root"

        # Remove colon for Windows drives (C: -> C)
        safe_name = safe_name.replace(":", "")

        return self.data_dir / f"{safe_name}.log"

    def _log_free_space(self, drive_path: str, free_space: int) -> None:
        """
        Log free space to a drive-specific log file.

        Args:
            drive_path: Drive path (e.g., "C:", "/")
            free_space: Free space in bytes
        """
        log_file = self._get_log_filename(drive_path)
        human_readable = self.format_bytes_multiple_units(free_space)
        timestamp = datetime.now().isoformat()

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{timestamp} {free_space} ({human_readable})\n")
        except Exception as e:
            print(f"Warning: Could not write to log file {log_file}: {e}")

    def _parse_log_file(self, log_file: Path) -> List[Tuple[datetime, int]]:
        """
        Parse log file and extract timestamps and free space values.

        Args:
            log_file: Path to the log file

        Returns:
            List of tuples (timestamp, free_space_bytes)
        """
        data_points = []

        if not log_file.exists():
            return data_points

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Count old format entries (without timestamps) to estimate their times
            old_format_count = 0
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(" ", 2)
                if len(parts) >= 1:
                    # Check if first part looks like a timestamp
                    first_part = parts[0]
                    if not (
                        "T" in first_part
                        or (
                            len(first_part) >= 10
                            and first_part[4] == "-"
                            and first_part[7] == "-"
                        )
                    ):
                        # Might be old format
                        try:
                            int(first_part)  # If it's a number, it's old format
                            old_format_count += 1
                        except ValueError:
                            pass

            old_format_index = 0
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Try to parse new format: ISO timestamp bytes (human_readable)
                # Format: "2024-01-01T12:00:00.123456 102176960512 (95 GB 201 MB)"
                # Or old format: "102176960512" or "102176960512 (95 GB 201 MB)"
                parts = line.split(" ", 2)

                if len(parts) >= 2:
                    timestamp_str = parts[0]
                    bytes_str = parts[1]

                    # Check if first part is an ISO timestamp
                    if "T" in timestamp_str or (
                        len(timestamp_str) >= 10
                        and timestamp_str[4] == "-"
                        and timestamp_str[7] == "-"
                    ):
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str)
                            free_space = int(bytes_str)
                            data_points.append((timestamp, free_space))
                            continue
                        except ValueError:
                            pass

                    # Old format: "bytes" or "bytes (human_readable)"
                    try:
                        free_space = int(parts[0])
                        # Assign estimated timestamps going backwards from now
                        # Assume 1 hour intervals between old entries
                        estimated_time = datetime.now() - timedelta(
                            hours=old_format_count - old_format_index
                        )
                        data_points.append((estimated_time, free_space))
                        old_format_index += 1
                        continue
                    except ValueError:
                        pass
                elif len(parts) == 1:
                    # Old format: just bytes on the line
                    try:
                        free_space = int(parts[0])
                        estimated_time = datetime.now() - timedelta(
                            hours=old_format_count - old_format_index
                        )
                        data_points.append((estimated_time, free_space))
                        old_format_index += 1
                        continue
                    except ValueError:
                        continue
        except Exception as e:
            print(f"Warning: Could not parse log file {log_file}: {e}")

        return data_points

    def _generate_graph(self, drive_path: str, log_file: Path) -> None:
        """
        Generate a graph showing free disk space over time for a drive.

        Args:
            drive_path: Drive path (e.g., "C:", "/")
            log_file: Path to the log file
        """
        try:
            import matplotlib

            matplotlib.use("Agg")  # Use non-interactive backend
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
        except ImportError:
            print(
                f"Warning: matplotlib not installed. Skipping graph generation for {drive_path}."
            )
            print("Install with: pip install matplotlib")
            return

        data_points = self._parse_log_file(log_file)

        if len(data_points) < 2:
            # Need at least 2 points to create a graph
            return

        # Sort by timestamp
        data_points.sort(key=lambda x: x[0])

        timestamps, free_spaces = zip(*data_points)

        # Convert bytes to GB for better readability
        free_spaces_gb = [space / (1024**3) for space in free_spaces]

        # Create the graph
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(
            timestamps,
            free_spaces_gb,
            marker="o",
            linestyle="-",
            linewidth=2,
            markersize=4,
        )

        ax.set_xlabel("Time", fontsize=12)
        ax.set_ylabel("Free Space (GB)", fontsize=12)
        ax.set_title(
            f"Free Disk Space Over Time - {drive_path}", fontsize=14, fontweight="bold"
        )
        ax.grid(True, alpha=0.3)

        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
        plt.xticks(rotation=45, ha="right")

        # Format y-axis to show GB
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.1f} GB"))

        plt.tight_layout()

        # Save the graph
        graph_file = log_file.with_suffix(".png")
        try:
            plt.savefig(graph_file, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"  Graph saved: {graph_file.name}")
        except Exception as e:
            print(f"Warning: Could not save graph {graph_file}: {e}")
            plt.close()

    def _get_notification_count_today(self) -> int:
        """
        Get the number of notifications sent today.

        Returns:
            Number of notifications sent today
        """
        today = date.today().isoformat()

        if not self.tracking_file.exists():
            return 0

        try:
            with open(self.tracking_file, "r", encoding="utf-8") as f:
                tracking_data = json.load(f)

            # Check if tracking data is for today
            if tracking_data.get("date") == today:
                return tracking_data.get("count", 0)
            else:
                # Different day, reset count
                return 0
        except (json.JSONDecodeError, KeyError):
            # Invalid or corrupted tracking file, reset
            return 0

    def _increment_notification_count(self) -> None:
        """Increment the notification count for today."""
        today = date.today().isoformat()

        try:
            if self.tracking_file.exists():
                with open(self.tracking_file, "r", encoding="utf-8") as f:
                    tracking_data = json.load(f)
            else:
                tracking_data = {}

            # Reset if it's a different day
            if tracking_data.get("date") != today:
                tracking_data = {"date": today, "count": 0}

            tracking_data["count"] = tracking_data.get("count", 0) + 1

            with open(self.tracking_file, "w", encoding="utf-8") as f:
                json.dump(tracking_data, f)
        except Exception as e:
            print(f"Warning: Could not update notification tracking: {e}")

    def send_pushover_notification(
        self, title: str, message: str, priority: int = 0
    ) -> bool:
        """
        Send notification via Pushover, respecting daily limit.

        Args:
            title: Notification title
            message: Notification message
            priority: Priority level (0=normal, 1=high, 2=emergency)

        Returns:
            True if successful, False if limit exceeded or error occurred
        """
        # Check daily limit if configured
        if self.max_push_notifications_per_day is not None:
            count_today = self._get_notification_count_today()
            if count_today >= self.max_push_notifications_per_day:
                print(
                    f"⚠️  Notification limit reached ({count_today}/{self.max_push_notifications_per_day} today). Skipping notification."
                )
                return False

        url = "https://api.pushover.net/1/messages.json"
        data = {
            "token": self.pushover_token,
            "user": self.pushover_user,
            "title": title,
            "message": message,
            "priority": priority,
        }

        try:
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()

            # Increment count only on success
            if self.max_push_notifications_per_day is not None:
                self._increment_notification_count()

            return True
        except Exception as e:
            print(f"Error sending Pushover notification: {e}")
            return False

    def check_and_notify(self):
        """Check disk space for all drives and send notifications if needed."""
        for drive_config in self.drives:
            drive_path = drive_config["path"]
            minimum_bytes = drive_config["minimum_bytes"]

            disk_info = self.get_disk_space(drive_path)
            if disk_info is None:
                continue

            free_space = disk_info["free"]
            total_space = disk_info["total"]
            used_space = disk_info["used"]
            free_percent = (free_space / total_space) * 100

            print(
                f"Drive {drive_path}: {self.format_bytes(free_space)} free "
                f"({free_percent:.1f}%) of {self.format_bytes(total_space)} "
                f"[threshold: {self.format_bytes(minimum_bytes)}]"
            )

            # Log free space to drive-specific log file
            self._log_free_space(drive_path, free_space)

            # Generate graph for this drive
            log_file = self._get_log_filename(drive_path)
            self._generate_graph(drive_path, log_file)

            if free_space < minimum_bytes:
                title = f"⚠️ Low Disk Space Alert: {drive_path}"
                message = (
                    f"Drive {drive_path} is running low on disk space!\n\n"
                    f"Free space: {self.format_bytes(free_space)}\n"
                    f"Used space: {self.format_bytes(used_space)}\n"
                    f"Total space: {self.format_bytes(total_space)}\n"
                    f"Free: {free_percent:.1f}%\n\n"
                    f"Minimum threshold: {self.format_bytes(minimum_bytes)}"
                )

                print(f"⚠️  ALERT: {drive_path} below threshold!")
                self.send_pushover_notification(title, message, priority=1)

    def run(self):
        """Run a single disk space check."""
        print(f"Checking disk space...")
        drive_list = []
        for drive_config in self.drives:
            path = drive_config["path"]
            threshold = self.format_bytes(drive_config["minimum_bytes"])
            drive_list.append(f"{path} (threshold: {threshold})")
        print(f"Monitoring drives: {', '.join(drive_list)}\n")

        self.check_and_notify()
        print("\nCheck complete.")


def load_settings(settings_file: str = "settings.json") -> Dict:
    """
    Load settings from a JSON file.

    Args:
        settings_file: Path to the settings JSON file

    Returns:
        Dictionary containing settings

    Raises:
        FileNotFoundError: If settings file doesn't exist
        json.JSONDecodeError: If settings file is invalid JSON
    """
    settings_path = Path(settings_file)

    if not settings_path.exists():
        raise FileNotFoundError(
            f"Settings file not found: {settings_file}\n"
            f"Please create a settings.json file with your configuration."
        )

    with open(settings_path, "r", encoding="utf-8") as f:
        settings = json.load(f)

    return settings


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor disk space and send Pushover notifications when space is low."
    )
    parser.add_argument(
        "--settings",
        "-s",
        type=str,
        default="settings.json",
        help="Path to settings JSON file (default: settings.json)",
    )

    args = parser.parse_args()

    try:
        settings = load_settings(args.settings)
        monitor = DiskSpaceMonitor(settings, args.settings)
        monitor.run()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"Error parsing settings file: {e}")
        print(f"Please check that {args.settings} contains valid JSON.")
        return 1
    except ValueError as e:
        print(f"Configuration error: {e}")
        print(f"\nPlease check your settings in {args.settings}.")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    main()
