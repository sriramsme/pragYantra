# Deployment status and prerequisites

The tested development host is Linux x86-64 with uv and Python 3.12. A Raspberry
Pi running a suitable 64-bit Linux distribution is a candidate host; the package
has not been installed, benchmarked, or tested on a Pi. No Pi camera, GPIO,
microcontroller firmware, serial transport or actuator driver is included.

## Install by capability

```bash
uv sync --locked                      # text, files, hosted services, SQLite
uv sync --locked --extra webcam       # optional OpenCV capture
uv sync --locked --extra audio        # optional sounddevice capture/playback
uv sync --locked --all-extras         # both device adapters and development tools
```

OpenCV uses its headless package. Audio-device access also requires system
PortAudio; on Debian-family systems the runtime library is commonly provided by
`libportaudio2`. Consult the OS/package and sounddevice documentation for the
selected machine instead of running the historical bootstrap scripts. No OS
package installation is performed by this repository. See
[sounddevice installation](https://python-sounddevice.readthedocs.io/en/latest/installation.html).

The native audio adapters assume little-endian PCM, as on the development machine
and typical current Pi Linux installations. Console async stdin currently targets
Linux terminals/pipes. Other operating systems have not been validated.

## Validate a selected edge host

Before claiming compatibility, record the exact board, OS/architecture, Python/uv
versions, power supply, camera/audio devices, and dependency wheel/build results.
Then run package checks, file-based hosted smoke tests, and only then short device
checks. Capture sustained-run results with acquisition age, request time, resource
usage, device failures and shutdown behavior. Hosted inference requires network
access and credentials; it moves model compute off the device, not sensor timing
or physical control responsibilities.

Use `pragyantra devices` to enumerate audio devices without capture/playback.
Select device indices explicitly when defaults are wrong. OS session permissions,
backend availability, sample rates and audio routing differ by deployment. Neither
OpenCV nor PortAudio timeouts establish a maximum native driver call duration.

The lockfile records dependency resolution; it does not establish ARM wheel
availability or real hardware functionality. C++ should enter the repository when
an actual firmware/native requirement is chosen, with its own build and device
tests. Hardware assumptions and interfaces must follow datasheets and measured
requirements rather than this candidate deployment sketch.
