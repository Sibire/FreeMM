# DIYgitizer

A Do-It-Yourself 5-DOF digitizer arm / coordinate measuring machine for under $200.

<img width="989" height="1029" alt="DIYgitizer arm" src="https://github.com/user-attachments/assets/77d42ab3-a628-4343-acd0-54771ef85c89" />

## What Is This?

DIYgitizer is a passive (no motors) measuring arm that you move by hand. Magnetic encoders at each joint track angles, forward kinematics computes the probe tip position in 3D, and a desktop app captures the data. The goal: digitize real objects into Fusion 360 and Inventor without spending thousands on commercial equipment.

**Three operating modes:**

- **CMM Mode** — Capture individual points, measure distances between them, export a dimension report
- **3D Digitizer Mode** — Scan a surface continuously, build a point cloud / mesh / parametric model, export for Fusion (PLY, STL, STEP)
- **2D Trace Mode** — Trace an outline, auto-detect lines/arcs/circles with dimensions, export a drawing (DXF, SVG)

All geometry decomposes into the simplest possible primitives — lines, arcs, circles, planes, cylinders, spheres — with dimensioned offsets. No splines. Every measurement is an individual dimension you can edit in Fusion.

## Hardware

### Kinematic Chain

```
Base Plate (clamped to desk)
  └─ J1: Base Yaw (360°)
       └─ Turret
            └─ J2: Shoulder Pitch (±105°)
                 └─ Upper Arm (300mm aluminum tube)
                      └─ J3: Elbow Pitch (±145°)
                           └─ Forearm (300mm aluminum tube)
                                └─ J4: Wrist Pitch (360°)
                                     └─ J5: Wrist Pitch 2 — perpendicular to J4 (±145°)
                                          └─ Probe (1mm ruby ball)
```

### Electronics

| Component | Details |
|-----------|---------|
| MCU | ESP32 DevKit V1 (38-pin) |
| Encoders | 5× AS5600 (12-bit magnetic, I2C) |
| I2C Mux | TCA9548A (resolves shared AS5600 address) |
| Display | 0.96" SSD1306 OLED (I2C) |
| Buttons | Sample (GPIO 26), Mode (GPIO 27), Foot Pedal (GPIO 25) |
| Probe | Suxing M2 ruby stylus (1mm ball, 20mm shaft) |

### Bill of Materials

All printed parts are PETG (60% infill, 4 walls). Total cost ~$150-200 depending on what you have on hand.

## Software

### Desktop App (Python / PyQt5)

```
cd desktop
pip install -r requirements.txt
python run.py
```

Check **Simulator** and click **Connect** to test without hardware.

**Features:**
- Live XYZ + joint angle readout
- CMM mode with point table and dimension list
- 3D viewport (OpenGL) with point cloud, mesh preview, and feature detection overlays
- 2D canvas with fitted features and dimension annotations
- Calibration wizard (1-2-3 block)
- Measurement rounding: 1mm / 0.1mm / 0.01mm (user setting)
- Export: DXF, SVG, PLY, CSV, STL, STEP

**Dependencies:** PyQt5, PyOpenGL, pyserial, numpy, scipy, ezdxf, trimesh. Optional: open3d (mesh), cadquery (STEP).

### Firmware (C++ / PlatformIO)

```
cd firmware
pio run                  # compile
pio run --target upload  # flash to ESP32
pio device monitor       # watch serial output
```

Streams `ANGLES,j1,j2,j3,j4,j5` at ~200Hz over USB serial (115200 baud). Responds to commands: `p` (sample point), `t` (toggle trace), `1`/`2`/`3` (set trace plane), `r` (reset).

### Link Lengths

The forward kinematics uses center-to-center joint distances. **These are placeholders** — measure your actual assembly in Fusion and update `firmware/src/config.h` and `desktop/diygitizer/config.py`:

```
BASE_HEIGHT = 50mm     # base plate surface to J2 axis
UPPER_ARM   = 150mm    # J2 to J3
FOREARM     = 130mm    # J3 to J4
WRIST_LINK  = 30mm     # J4 to J5
PROBE_LEN   = 20mm     # J5 to ruby ball center
```

## Calibration

Use a 1-2-3 block (25.4 × 50.8 × 76.2mm) — cheap, precise, widely available. The app's calibration wizard walks you through touching each face, then computes scale factors and joint offsets to minimize error.

## Accuracy

- AS5600: ±1° typical (12-bit)
- Expected tip accuracy: ±1-2mm calibrated, ±3-5mm uncalibrated
- Probe compensation: 0.5mm ball radius, applied automatically
- This is a digitizer, not a metrology instrument — but it's plenty for making dimensioned models from physical objects

## Project Structure

```
DIYgitizer/
├── firmware/                    # ESP32 PlatformIO project
│   ├── platformio.ini
│   └── src/
│       ├── main.cpp             # Main loop
│       ├── config.h             # Pins, link lengths, constants
│       ├── encoders.*           # AS5600 via TCA9548A mux
│       ├── kinematics.*         # 5-DOF forward kinematics
│       ├── serial_protocol.*    # USB serial protocol
│       ├── buttons.*            # Debounced input
│       ├── display.*            # SSD1306 OLED
│       └── modes.*              # State machine
│
└── desktop/                     # Python desktop app
    ├── run.py                   # Entry point
    ├── requirements.txt
    └── diygitizer/
        ├── app.py               # MainWindow + DataStore
        ├── config.py            # Link lengths, rounding
        ├── connection/          # Serial + simulator
        ├── models/              # Data classes
        ├── modes/
        │   ├── cmm/             # Point capture + dimensions
        │   ├── digitizer/       # 3D scan + mesh + features
        │   └── trace/           # 2D trace pipeline
        ├── calibration/         # 1-2-3 block wizard
        ├── export/              # DXF, SVG, PLY, STL, STEP, CSV
        └── widgets/             # Shared UI components
```

## Status

- [x] Full CAD assembly in Fusion 360
- [x] ESP32 firmware (5-DOF FK, serial protocol, OLED, buttons)
- [x] Desktop app with all three modes
- [x] Geometry pipeline (2D feature fitting)
- [x] 3D feature detection (RANSAC plane/sphere/cylinder)
- [x] Export: DXF, SVG, PLY, STL, STEP, CSV
- [x] Calibration wizard
- [x] Built-in simulator
- [ ] Print and assemble hardware
- [ ] Measure actual link lengths from assembly
- [ ] First real-hardware test
- [ ] Tune calibration procedure

## License

TBD

