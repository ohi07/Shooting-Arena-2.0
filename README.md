#  Shooting Arena 2.0

An **updated FPS Training Ground** built with **Python + PyOpenGL + GLUT**.  
This version expands on the original **Shooting Arena** with **better UI, smoother recoil, enhanced grenades/smokes, and improved controls**.

---

##  New & Improved Features (v2.0)
- **Enhanced Enemy AI**
  - Smarter dodging, sidestepping, and boundary repelling
  - Fireback unlocks after 10 kills  
- **Weapons**
  - **AK-47** with recoil system (single, burst, auto)
  - **AWP sniper** with zoom + scoped overlay
- **Better Grenades**
  - Frag grenades can kill multiple enemies at once
  - Smoke grenades now **blend with transparency** and block line-of-sight
- **Combat System**
  - Headshots instantly kill; 2 headshots restore +10 HP
  - Wallbang detection (kills through obstacles)
  - Killfeed messages for recent kills
- **HUD & Menus**
  - Health bar with dynamic color
  - Expanded kill statistics (shots, misses, head/body/grenade kills, wallbangs, time)
  - Full map overlay
  - Improved pause menu with click support
- **Controls Upgrade**
  - Mouse look + recoil kick
  - Mouse left/right: Fire / Toggle scope/mode
  - Crosshair toggle
  - Cleaner scope graphics & overlays

---

##  Controls
```
Movement:
  W/S – Forward / Backward
  A/D – Rotate Left / Right
  SPACE – Jump

Combat:
  LMB – Fire (hold for AK auto/burst)
  RMB – Scope (AWP) / Switch fire mode (AK)
  V   – Swap AK ↔ AWP
  G   – Frag Grenade
  T   – Smoke Grenade

View & HUD:
  Z   – Zoom (AWP only)
  E   – Toggle Crosshair
  C   – X-ray cheat (wallhack)
  X   – Map Overlay

System:
  Q   – End Session
  ESC – Menu (Continue / Restart / Exit)
```

---

##  Requirements
- Python 3.x  
- [PyOpenGL](https://pypi.org/project/PyOpenGL/)  
- [PyOpenGL_accelerate](https://pypi.org/project/PyOpenGL-accelerate/) *(optional but faster)*  
- GLUT (`freeglut` or system OpenGL library)

Install with:
```bash
pip install PyOpenGL PyOpenGL_accelerate
```

---

##  How to Run
```bash
python Shooting-Arena2.0.py
```

A window will open titled:  
**Shooting-Arena 2.0 by Ohi**

---

##  Gameplay Notes
- **Headshots**: Instant kill, heal +10 HP every 2 headshots (if below 100 HP)  
- **Grenades**: Explode after ~2 seconds or 3 bounces  
- **Smokes**: Block both vision & bullets while active  
- **Killfeed**: Displays recent kills (“HEADSHOT”, “WALLBANG BODY”, etc.)  
- **Enemy AI**: Smarter than v1.0, avoids walls, fires back once you reach 10 kills  

---

##  Credits
Developed by **Ohi**  
Upgraded to **Shooting Arena 2.0** for a more advanced FPS training experience.
