# Disk Space Monitor

A Python script that checks disk space once and sends Pushover notifications when disk space falls below a configured threshold. Designed to be run via cron job or scheduled task.

## Features

- ✅ Human-friendly disk space units (MB, GB, TB, etc.)
- ✅ Pushover notifications for low disk space alerts
- ✅ Cross-platform support (Windows, Linux, macOS)
- ✅ Monitor multiple drives
- ✅ Runs once per execution (perfect for cron jobs)
- ✅ Per-drive log files tracking free space over time
- ✅ Automatic graph generation showing disk space trends

## Setup

1. **Install dependencies:**
   
   **Using a virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
   
   **Or using pipx (for isolated installation):**
   ```bash
   pipx install -r requirements.txt
   ```
   
   **Direct installation (not recommended on Debian/Ubuntu):**
   ```bash
   pip install -r requirements.txt
   ```
   
   > **Note:** On Debian/Ubuntu systems, you may encounter an error about system packages. See the [Troubleshooting](#troubleshooting) section below.

2. **Get Pushover credentials:**
   - Sign up at https://pushover.net/
   - Get your User Key from the dashboard
   - Create an application at https://pushover.net/apps/build to get an API Token

3. **Configure the script:**
   Copy `settings.example.json` to `settings.json`:
   ```bash
   cp settings.example.json settings.json
   ```
   
   Then edit `settings.json` with your configuration:
   ```json
   {
     "pushover_token": "YOUR_PUSHOVER_API_TOKEN",
     "pushover_user": "YOUR_PUSHOVER_USER_KEY",
     "max_push_notifications_per_day": 10,
     "drives": [
       {
         "path": "C:",
         "minimum_disk_space": "10GB"
       }
     ]
   }
   ```
   
   **Note:** `settings.json` and `.notification_tracking.json` are in `.gitignore` to protect your credentials and tracking data.

## Usage

Run the script manually (uses `settings.json` by default):
```bash
python monitor_disk_space.py
```

Or specify a different settings file:
```bash
python monitor_disk_space.py --settings /path/to/custom_settings.json
```

Set up a cron job (Linux/Mac) or scheduled task (Windows) to run it periodically.

## Setting Up Cron Jobs (Linux/Mac)

### Step 1: Find Python Path

First, find the full path to your Python interpreter:
```bash
which python3
# or
which python
```

Common paths:
- `/usr/bin/python3`
- `/usr/local/bin/python3`
- `/opt/homebrew/bin/python3` (macOS with Homebrew)

### Step 2: Edit Crontab

Open your crontab for editing:
```bash
crontab -e
```

If this is your first time, you may be asked to choose an editor. Choose your preferred editor (nano is beginner-friendly).

### Step 3: Add Cron Job Line

Add a line to your crontab. The format is:
```
* * * * * /path/to/python /path/to/monitor_disk_space.py [--settings /path/to/settings.json]
```

**Cron time format:**
```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
* * * * *
```

**Common examples:**

Run every hour:
```bash
0 * * * * /usr/bin/python3 /root/monitor_disk_space/monitor_disk_space.py
```

Run daily at 9:00 AM:
```bash
0 9 * * * /usr/bin/python3 /root/monitor_disk_space/monitor_disk_space.py
```

Run every 6 hours:
```bash
0 */6 * * * /usr/bin/python3 /root/monitor_disk_space/monitor_disk_space.py
```

Run daily at 2:30 AM:
```bash
30 2 * * * /usr/bin/python3 /root/monitor_disk_space/monitor_disk_space.py
```

Run with custom settings file:
```bash
0 * * * * /usr/bin/python3 /root/monitor_disk_space/monitor_disk_space.py --settings /root/monitor_disk_space/settings.ubuntu.json
```

**Important:** Use absolute paths for both Python and the script. Relative paths won't work in cron.

### Step 4: Save and Exit

- **nano**: Press `Ctrl+X`, then `Y`, then `Enter`
- **vim**: Press `Esc`, type `:wq`, then `Enter`
- **emacs**: Press `Ctrl+X` then `Ctrl+S` to save, `Ctrl+X` then `Ctrl+C` to exit

### Step 5: Verify Cron Job

List your cron jobs to verify it was added:
```bash
crontab -l
```

Check cron logs to see if it's running:
```bash
# On Linux
grep CRON /var/log/syslog
# or
journalctl -u cron

# On macOS
grep cron /var/log/system.log
```

### Step 6: Test Manually

Before waiting for the cron job to run, test the script manually:
```bash
/usr/bin/python3 /path/to/monitor_disk_space.py
```

Make sure it works correctly before relying on the cron job.

## Windows Task Scheduler

On Windows, use Task Scheduler instead of cron:

1. Open **Task Scheduler** (search for it in Start menu)
2. Click **Create Basic Task** or **Create Task**
3. Set a name and description
4. Choose trigger (Daily, Weekly, etc.) and set the time
5. Choose **Start a program** as the action
6. Set:
   - **Program/script**: `C:\Python3\python.exe` (or your Python path)
   - **Add arguments**: `monitor_disk_space.py --settings settings.Windows.json`
   - **Start in**: `C:\path\to\monitor_disk_space\` (directory containing the script)
7. Save the task

The script will:
- Check disk space once per execution
- Display current disk space information
- Log free space to a per-drive log file (e.g., `C.log`, `root.log`)
- Generate graphs showing disk space trends over time (e.g., `C.png`, `root.png`)
- Send Pushover notifications when disk space is below the threshold
- Exit after completing the check

**Log Files:** Each monitored drive gets its own log file (e.g., `C.log` for `C:`, `root.log` for `/`). Each line contains a timestamp, free space in bytes, and human-readable format (e.g., `2024-01-01T12:00:00 102176960512 (95 GB 201 MB)`). Log files are stored in the `data/` folder.

**Graph Files:** For each drive with at least 2 log entries, a PNG graph is automatically generated (e.g., `C.png`, `root.png`) showing free disk space over time. Graphs are updated each time the script runs and are saved in the `data/` folder.

**Data Folder:** All generated files (logs, graphs, and notification tracking) are stored in the folder specified by the `data_folder` setting (default: `data/`). The folder path can be relative to the settings file directory or an absolute path. The folder is created automatically if it doesn't exist.

## Configuration Options

- **pushover_token**: Your Pushover API token
- **pushover_user**: Your Pushover user key
- **max_push_notifications_per_day**: (Optional) Maximum number of push notifications to send per day. Prevents notification spam if disk space fluctuates around the threshold. If not specified, there is no limit. Default: unlimited
- **data_folder**: (Optional) Path to folder for storing logs, graphs, and tracking files. Can be relative (to settings file directory) or absolute. Default: `"data"`
- **drives**: List of drive configurations. Each drive must specify:
  - **path**: Drive path (e.g., `"C:"` on Windows, `"/"` on Linux/Mac)
  - **minimum_disk_space**: Alert threshold in human-friendly format:
    - `"500MB"` - 500 megabytes
    - `"10GB"` - 10 gigabytes
    - `"1TB"` - 1 terabyte

  Example:
  ```json
  "drives": [
    {
      "path": "C:",
      "minimum_disk_space": "10GB"
    },
    {
      "path": "D:",
      "minimum_disk_space": "5GB"
    }
  ]
  ```

**Notes:**
- The notification count resets daily at midnight. A tracking file (`.notification_tracking.json`) is created in the same directory as your settings file to track daily counts.
- Log files are automatically created for each monitored drive (e.g., `C.log` for drive `C:`, `root.log` for `/`). Each line contains a timestamp, free space in bytes, and human-readable format (e.g., `2024-01-01T12:00:00 102176960512 (95 GB 201 MB)`). Log files are stored in the folder specified by `data_folder` (default: `data/`).
- Graph files (PNG images) are automatically generated for each drive showing free disk space trends over time. Graphs require at least 2 log entries and are updated each time the script runs. Requires `matplotlib` to be installed. Graph files are stored in the folder specified by `data_folder` (default: `data/`).
- All generated files (logs, graphs, and notification tracking) are stored in the folder specified by the `data_folder` setting. The folder path can be relative to the settings file directory or an absolute path. The folder is created automatically if it doesn't exist.

## Examples

**Monitor single drive:**
```json
{
  "pushover_token": "abc123...",
  "pushover_user": "xyz789...",
  "drives": [
    {
      "path": "C:",
      "minimum_disk_space": "5GB"
    }
  ]
}
```

**Monitor multiple drives with different thresholds:**
```json
{
  "pushover_token": "abc123...",
  "pushover_user": "xyz789...",
  "drives": [
    {
      "path": "C:",
      "minimum_disk_space": "20GB"
    },
    {
      "path": "D:",
      "minimum_disk_space": "5GB"
    },
    {
      "path": "E:",
      "minimum_disk_space": "1GB"
    }
  ]
}
```

**Monitor multiple drives on Linux:**
```json
{
  "pushover_token": "abc123...",
  "pushover_user": "xyz789...",
  "drives": [
    {
      "path": "/",
      "minimum_disk_space": "20GB"
    },
    {
      "path": "/home",
      "minimum_disk_space": "50GB"
    },
    {
      "path": "/var",
      "minimum_disk_space": "5GB"
    }
  ]
}
```

## Troubleshooting

### Python Installation Issues on Debian/Ubuntu

If you encounter an error like this when trying to install dependencies:

```
error: externally-managed-environment

× This environment is externally managed
╰─> To install Python packages system-wide, try 'apt install
    python3-xyz', where xyz is the package you are trying to
    install.

If you wish to install a non-Debian-packaged Python package,
create a virtual environment using python3 -m venv path/to/venv.
Then use path/to/venv/bin/python and path/to/venv/bin/pip. Make
sure you have python3-full installed.

If you wish to install a non-Debian packaged Python application,
it may be easiest to use pipx install xyz, which will manage a
virtual environment for you. Make sure you have pipx installed.
```

This is a protection mechanism on Debian/Ubuntu systems (PEP 668) that prevents breaking system Python packages. Here are the recommended solutions:

**Option 1: Use a Virtual Environment (Recommended)**
```bash
# Create a virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the script using the virtual environment's Python
venv/bin/python monitor_disk_space.py
```

**Option 2: Use pipx**
```bash
# Install pipx if not already installed
sudo apt install pipx

# Install packages in isolated environments
pipx install requests matplotlib

# Or install the script itself
pipx install -e .
```

**Option 3: Install Required System Packages**
```bash
# Install Python packages via apt (if available)
sudo apt install python3-requests python3-matplotlib
```

**Option 4: Override Protection (Not Recommended)**
```bash
# Only use this if you understand the risks
pip install --break-system-packages -r requirements.txt
```

> **Warning:** Using `--break-system-packages` can break your system Python installation. Only use this if you know what you're doing.

For cron jobs, make sure to use the full path to the Python interpreter in your virtual environment:
```bash
# Example cron job using venv
0 * * * * /path/to/monitor_disk_space/venv/bin/python /path/to/monitor_disk_space/monitor_disk_space.py
```

