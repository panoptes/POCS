# Migration Plan: Supervisord to Systemd User Services

## Background
POCS currently uses `supervisord` to manage background services (config server, hardware APIs, weather, etc.). While functional, `supervisord` lacks native OS integration, true dependency graph resolution (relying on `startsecs` instead of explicit dependencies), and robust log management compared to `systemd` and `journald`. Transitioning to `systemd` user services will provide a more native, resilient, and standard environment, particularly well-suited for Raspberry Pi deployments.

## Architecture

1.  **User-Level Services**: We will use `systemd --user` so that the `panoptes` user can manage their own services without requiring `sudo` for everyday operations. 
2.  **Linger**: We must enable lingering for the `panoptes` user (`loginctl enable-linger panoptes`) so these user services start on boot, even if the user hasn't interactively logged in.
3.  **Target Grouping**: We will define a `pocs.target` to group all related services. This allows the user to run a single command (`systemctl --user start pocs.target`) to bring up the entire observatory.

## Service Mapping

We will convert each program in `conf_files/pocs-supervisord.conf` into a corresponding `systemd` service file located in `~/.config/systemd/user/`.

### Core Infrastructure
**`pocs-config.service`**
- **ExecStart**: `panoptes-utils config run --host 0.0.0.0 --port 6563 --config-file conf_files/pocs.yaml`
- **Dependencies**: None.

### Hardware Services
**`pocs-mount.service`, `pocs-camera.service`, `pocs-scheduler.service`**
- **ExecStart**: `uvicorn --host 0.0.0.0 --port <PORT> panoptes.pocs.services.<NAME>_api:app`
- **Dependencies**: `After=pocs-config.service`, `Requires=pocs-config.service`

### Auxiliary Services
**`pocs-power-monitor.service`, `pocs-jupyter-server.service`, `pocs-weather-reader.service`, `pocs-metadata-uploader.service`**
- Configured similarly, referencing their respective commands and depending on `pocs-config.service` where applicable.

## Implementation Steps

### 1. Create Systemd Templates
Create a new directory `conf_files/systemd/` containing the `.service` and `.target` template files. These templates will use relative paths where possible or be dynamically updated during installation.

### 2. Update Installer Scripts
Modify `resources/scripts/install/install-services.sh`:
- **Remove**: Code that configures `supervisord` and modifies `/etc/supervisor/supervisord.conf`.
- **Add**: 
  - `mkdir -p ~/.config/systemd/user/`
  - Copy all files from `conf_files/systemd/` to `~/.config/systemd/user/`.
  - Dynamically replace paths (like `/home/panoptes`) with `${HOME}` using `sed` in the copied service files.
  - `systemctl --user daemon-reload`
  - `systemctl --user enable pocs.target`
  - Instruct the user (or automate if using `sudo` installer wrapper) to run `sudo loginctl enable-linger $USER`.

### 3. Update Dependencies
- Modify `install-system-deps.sh` to remove `supervisor` if it is currently being installed via `apt`.

### 4. Update Documentation
- **`AGENTS.md` & `README.md`**: Replace references to `supervisorctl` or `pocs-supervisord.conf` with `systemctl --user status pocs.target`, `journalctl --user -u pocs-mount.service`, etc.

### 5. Cleanup
- Delete `conf_files/pocs-supervisord.conf`.

## Note
This plan is a reference document for future work. It is not intended to be executed automatically by the agent at this time.
