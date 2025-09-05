# ---------------- Shooting-Arena 2.0  ----------------
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import time, math, sys, os, random

# ---------------- Window / Camera ----------------
win_w, win_h = 1280, 900
aspect = win_w / float(win_h)
FOVY_NORM, FOVY_ZOOM = 95.0, 38.0
zoomed = False
scope_on = False

# ---------------- Player ----------------
Px, Py, Pz = 0.0, -900.0, 0.0
Pangle, Pitch = 90.0, 0.0
Pspeed = 280.0
PLAYER_RADIUS = 20.0
EYE_HEIGHT = 65.0

# jump
Pvz = 0.0
JUMP_V0 = 420.0
GRAVITY_PLAYER = -980.0
GROUND_EPS = 0.01

# input state
key_W = key_S = key_A = key_D = False
mouse_left_down = False

# overlays
map_overlay = False
crosshair_on = True  # default for AK; we switch when swapping weapons

# time / session
play_time = 0.0
session_over = False
session_reason = "Quit"
menu_active = False
menu_choice = 0
menu_click_zones = []

# ---------------- World ----------------
grid_l, WALL_H = 1400, 170.0
MAZE = [
    (-grid_l,0,40,grid_l,WALL_H), (grid_l,0,40,grid_l,WALL_H),
    (0,-grid_l,grid_l,40,WALL_H), (0,grid_l,grid_l,40,WALL_H),
    (0,0,420,40,WALL_H), (0,420,300,40,WALL_H), (0,-420,300,40,WALL_H),
    (-600,0,40,420,WALL_H), (600,0,40,420,WALL_H),
    (-280,620,260,40,WALL_H), (280,-620,260,40,WALL_H),
    (-800,300,40,260,WALL_H), (800,-300,40,260,WALL_H),
    (-220,-240,140,40,WALL_H), (220,240,140,40,WALL_H),
]
CRATES = [
    (-150,60,60,60,120), (180,-120,70,50,120), (420,260,65,65,120),
    (-420,-260,65,65,120), (0,620,90,50,120), (0,-620,90,50,120),
    (820,60,80,80,120), (-820,-60,80,80,120), (520,520,80,70,120),
    (-520,-520,80,70,120), (260,880,70,60,120), (-260,-880,70,60,120)
]
def all_obstacles():
    for o in MAZE:  yield o
    for o in CRATES: yield o

# ---------------- Enemies ----------------
NUM_ENEMIES = 5
enemies = []   # {x,y,z,hp,next_shot,unstick}
HEAD_R = 14.0
BODY_W, BODY_H, BODY_D = 28.0, 50.0, 18.0
LEG_H = 20.0
ENEMY_RADIUS = 22.0
ENEMY_SPEED = 145.0  # slight boost

E_BULLETS = []      # enemy bullets
E_B_SPD   = 800.0
player_hp = 100
hs_for_heal = 0  # every 2 headshots while hurt => +10 HP

# ---------------- Player bullets ----------------
bullets = []
AWP_SPEED, AWP_CD, B_LIFE, B_SIZE = 1600.0, 1.2, 1.25, 8.0
_last_shot = -1e9

# AK weapon
AK_SPEED = 1400.0
AK_CD_SINGLE = 0.14
AK_CD_AUTO   = 0.10
AK_BURST_SPACING = 0.07
weapon = "AK"            # "AK" or "AWP"
ak_mode = "single"       # "single" | "burst" | "auto"
ak_next_fire = 0.0
ak_burst_left = 0

# ---------------- Grenades / Smoke ----------------
GRAVITY = -900.0
grenades  = []
explosions= []

SMOKES = []
SMOKE_EMIT_TIME   = 6.0
SMOKE_PUFF_LIFE   = 7.0
SMOKE_PUFF_SIZE   = 26.0
SMOKE_BURST_RATE  = 8
SMOKE_RADIUS_VIS  = 280.0

class Puff:
    __slots__=("x","y","z","vx","vy","vz","born")
    def __init__(self,x,y,z):
        self.x,self.y,self.z = x,y,z
        ang = random.uniform(0, 2*math.pi)
        self.vx = math.cos(ang)*30.0
        self.vy = math.sin(ang)*30.0
        self.vz = 120.0 + random.uniform(0,60)
        self.born = time.time()

FRAG_FUSE, FRAG_RADIUS = 2.0, 150.0

# ---------------- Stats / Feed ----------------
headshots = bodykills = grenade_kills = shots_fired = missed_shots = wallbang_kills = 0
kill_feed = []

# ---------------- Cheats ----------------
xray = False

# ---------------- Helpers ----------------
def clamp(v,lo,hi): return lo if v<lo else hi if v>hi else v
def circle_aabb(px,py,pr,cx,cy,sx,sy):
    dx=max(abs(px-cx)-sx,0.0); dy=max(abs(py-cy)-sy,0.0)
    return (dx*dx+dy*dy)<=pr*pr
def blocked(nx,ny):
    if abs(nx)>grid_l-PLAYER_RADIUS or abs(ny)>grid_l-PLAYER_RADIUS: return True
    for (cx,cy,sx,sy,h) in all_obstacles():
        if circle_aabb(nx,ny,PLAYER_RADIUS,cx,cy,sx,sy): return True
    return False
def enemy_blocked(nx,ny):
    if abs(nx)>grid_l-ENEMY_RADIUS or abs(ny)>grid_l-ENEMY_RADIUS: return True
    for (cx,cy,sx,sy,h) in all_obstacles():
        if circle_aabb(nx,ny,ENEMY_RADIUS,cx,cy,sx,sy): return True
    return False
def point_in_obstacle(px,py):
    for (cx,cy,sx,sy,h) in all_obstacles():
        if (cx-sx)<=px<=(cx+sx) and (cy-sy)<=py<=(cy+sy): return True
    return False
def right_vec_from_yaw(yaw):
    y=math.radians(yaw); return -math.sin(y), math.cos(y)
def norm2(x,y):
    d=math.hypot(x,y); return (x/d,y/d) if d else (0.0,0.0)

def has_line_of_sight(px,py, ex,ey, step=18.0):
    dx,dy=ex-px,ey-py; dist=math.hypot(dx,dy)
    if dist==0: return True
    ux,uy=dx/dist,dy/dist; t=0.0
    while t<=dist:
        x=px+ux*t; y=py+uy*t
        if point_in_obstacle(x,y): return False
        for s in SMOKES:
            for p in s["puffs"]:
                if (x-p.x)**2 + (y-p.y)**2 <= (SMOKE_RADIUS_VIS*0.45)**2:
                    return False
        t+=step
    return True

# ---------------- Camera ----------------
def setupCamera():
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluPerspective(FOVY_ZOOM if (zoomed and weapon=="AWP") else FOVY_NORM, aspect, 0.1, 5000.0)
    glMatrixMode(GL_MODELVIEW); glLoadIdentity()
    ex,ey,ez=Px,Py,Pz+EYE_HEIGHT
    fx=math.cos(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fy=math.sin(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fz=math.sin(math.radians(Pitch))
    gluLookAt(ex,ey,ez, ex+fx,ey+fy,ez+fz, 0,0,1)

# ---------------- Viewmodels ----------------
def draw_awp():
    if scope_on or menu_active or map_overlay: return
    ex,ey,ez=Px,Py,Pz+EYE_HEIGHT
    fx=math.cos(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fy=math.sin(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fz=math.sin(math.radians(Pitch))
    rx,ry=right_vec_from_yaw(Pangle)
    side,drop,forward=14.0,10.0,22.0
    bx=ex+rx*side+fx*forward; by=ey+ry*side+fy*forward; bz=ez-drop+fz*2.0
    glPushMatrix(); glTranslatef(bx,by,bz); glRotatef(Pangle,0,0,1); glRotatef(-Pitch,0,1,0)
    glColor3f(0.18,0.18,0.18); glPushMatrix(); glScalef(40,10,10); glutSolidCube(1.0); glPopMatrix()
    glColor3f(0.28,0.28,0.28); glPushMatrix(); glTranslatef(22,0,0); glRotatef(90,0,1,0)
    gluCylinder(gluNewQuadric(),2.8,2.6,70,12,1); glPopMatrix()
    glColor3f(0.12,0.12,0.12); glPushMatrix(); glTranslatef(5,0,6); glRotatef(90,0,1,0)
    gluCylinder(gluNewQuadric(),3.5,3.2,20,12,1); glPopMatrix()
    glPopMatrix()

def draw_ak():
    if menu_active or map_overlay: return
    ex,ey,ez=Px,Py,Pz+EYE_HEIGHT
    fx=math.cos(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fy=math.sin(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fz=math.sin(math.radians(Pitch))
    rx,ry=right_vec_from_yaw(Pangle)
    side,drop,forward=14.0,10.0,20.0
    bx=ex+rx*side+fx*forward; by=ey+ry*side+fy*forward; bz=ez-drop+fz*2.0
    glPushMatrix(); glTranslatef(bx,by,bz); glRotatef(Pangle,0,0,1); glRotatef(-Pitch,0,1,0)
    # stock (orange), body (dark), barrel
    glColor3f(0.95,0.55,0.12); glPushMatrix(); glTranslatef(-10,0,0); glScalef(22,10,10); glutSolidCube(1.0); glPopMatrix()
    glColor3f(0.12,0.12,0.12); glPushMatrix(); glScalef(30,10,12); glutSolidCube(1.0); glPopMatrix()
    glColor3f(0.65,0.65,0.65); glPushMatrix(); glTranslatef(16,0,2); glRotatef(90,0,1,0)
    gluCylinder(gluNewQuadric(),2.2,2.0,34,10,1); glPopMatrix()
    glPopMatrix()

def draw_weapon():
    if weapon=="AK": draw_ak()
    else: draw_awp()

def muzzle_world_pos():
    ex,ey,ez=Px,Py,Pz+EYE_HEIGHT
    fx=math.cos(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fy=math.sin(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fz=math.sin(math.radians(Pitch))
    rx,ry=right_vec_from_yaw(Pangle)
    side,drop,forward = (14.0,10.0,22.0) if weapon=="AWP" else (14.0,10.0,18.0)
    return (ex+rx*side+fx*(forward+60), ey+ry*side+fy*(forward+60), ez-drop+fz*60)

# ---------------- Enemies ----------------
def draw_enemy(e, color=(0.0,0.6,0.0)):
    if map_overlay: return
    glPushMatrix(); glTranslatef(e["x"],e["y"],e["z"])
    glColor3f(color[0]*0.8,color[1]*0.8,color[2]*0.8)
    for s in (-BODY_W*0.25,BODY_W*0.25):
        glPushMatrix(); glTranslatef(s,0,LEG_H*0.5); glScalef(BODY_W*0.4,BODY_D*0.6,LEG_H); glutSolidCube(1.0); glPopMatrix()
    glColor3f(*color)
    glPushMatrix(); glTranslatef(0,0,LEG_H+BODY_H*0.5); glScalef(BODY_W,BODY_D,BODY_H); glutSolidCube(1.0); glPopMatrix()
    glColor3f(0,0,0); glPushMatrix(); glTranslatef(0,0,LEG_H+BODY_H+HEAD_R); gluSphere(gluNewQuadric(),HEAD_R,12,12); glPopMatrix()
    # simple rifle on right chest
    glColor3f(0.3,0.3,0.3); glPushMatrix(); glTranslatef(BODY_W*0.45,0,LEG_H+BODY_H*0.7); glRotatef(90,0,1,0)
    gluCylinder(gluNewQuadric(),3,2.5,25,12,1); glPopMatrix()
    glPopMatrix()

def spawn_enemy():
    while True:
        x=random.randint(-grid_l+100,grid_l-100); y=random.randint(-grid_l+100,grid_l-100)
        if not point_in_obstacle(x,y): return {"x":float(x),"y":float(y),"z":0.0,"hp":2,"next_shot":time.time()+9999,"unstick":0.0}

def reset_enemies():
    global enemies; enemies=[spawn_enemy() for _ in range(NUM_ENEMIES)]

def update_enemies(dt):
    prx,pry=right_vec_from_yaw(Pangle)
    for e in enemies:
        # flee + sidestep logic
        toE_x,toE_y=e["x"]-Px,e["y"]-Py
        s = 1.0 if (prx*toE_x + pry*toE_y) < 0.0 else -1.0
        awayx,awayy=norm2(toE_x,toE_y)
        sidex,sidey=prx*s,pry*s
        desx,desy=norm2(awayx*0.7+sidex*0.3, awayy*0.7+sidey*0.3)
        base=ENEMY_SPEED; yaw=math.degrees(math.atan2(desy,desx))
        best=None
        for off in (0,+40,-40,+80,-80,+120,-120,+160,-160,+180):
            a=math.radians(yaw+off); dirx,diry=math.cos(a),math.sin(a)
            step=base*dt; nx,ny=e["x"]+dirx*step, e["y"]+diry*step
            if enemy_blocked(nx,ny): continue
            # prefer inward if near boundary
            margin = grid_l - max(abs(nx),abs(ny))
            score=(1.0 if margin<120 else 0.0) + random.random()*0.25
            if (best is None) or (score>best[0]): best=(score,nx,ny)
        if best:
            e["x"],e["y"]=best[1],best[2]
        # bounce/repel from borders
        repel = 40.0*dt
        if e["x"]>grid_l-ENEMY_RADIUS-1: e["x"]-=repel
        if e["x"]<-grid_l+ENEMY_RADIUS+1: e["x"]+=repel
        if e["y"]>grid_l-ENEMY_RADIUS-1: e["y"]-=repel
        if e["y"]<-grid_l+ENEMY_RADIUS+1: e["y"]+=repel

# enemy fire (starts at 10 kills)
def enemy_try_fire(now):
    total_kills=headshots+bodykills+grenade_kills
    if total_kills < 10 or map_overlay:   # unlock threshold
        return
    head_z = Pz + EYE_HEIGHT
    for e in enemies:
        if e["next_shot"] > now + 3.0:
            e["next_shot"] = now + random.uniform(0.4, 1.2)
        if now < e["next_shot"]: continue
        if not has_line_of_sight(e["x"],e["y"], Px,Py):
            e["next_shot"] = now + 0.6; continue
        # Fire from a muzzle offset pointing toward player
        tx,ty,tz = Px,Py,(head_z if random.random()<0.5 else Pz+BODY_H*0.6)
        dx,dy = tx-e["x"], ty-e["y"]; dist=max(1e-6, math.hypot(dx,dy))
        ux,uy = dx/dist, dy/dist
        # right-hand offset
        rx,ry = -uy, ux
        origin_x = e["x"] + ux*18.0 + rx*6.0
        origin_y = e["y"] + uy*18.0 + ry*6.0
        origin_z = e["z"] + LEG_H + BODY_H*0.7
        dz = tz - origin_z; dist3 = math.sqrt((tx-origin_x)**2+(ty-origin_y)**2+dz*dz)
        vx,vy,vz = (tx-origin_x)/dist3, (ty-origin_y)/dist3, dz/dist3
        spread = 0.03
        vx += random.uniform(-spread,spread); vy += random.uniform(-spread,spread); vz += random.uniform(-spread,spread)
        d = math.sqrt(vx*vx+vy*vy+vz*vz); vx,vy,vz = vx/d,vy/d,vz/d
        E_BULLETS.append({"x":origin_x,"y":origin_y,"z":origin_z,
                          "vx":vx*E_B_SPD,"vy":vy*E_B_SPD,"vz":vz*E_B_SPD})
        e["next_shot"] = now + random.uniform(1.4, 2.6)

def step_enemy_bullets(dt):
    global player_hp
    alive=[]
    for b in E_BULLETS:
        nx=b["x"]+b["vx"]*dt; ny=b["y"]+b["vy"]*dt; nz=b["z"]+b["vz"]*dt
        if abs(nx)>grid_l or abs(ny)>grid_l or point_in_obstacle(nx,ny):
            continue
        # smoke blocks enemy bullets
        blocked_by_smoke=False
        for s in SMOKES:
            for p in s["puffs"]:
                if (nx-p.x)**2+(ny-p.y)**2 <= (SMOKE_RADIUS_VIS*0.55)**2:
                    blocked_by_smoke=True; break
            if blocked_by_smoke: break
        if blocked_by_smoke: continue
        headx,heady,headz = Px,Py,Pz+EYE_HEIGHT
        if (nx-headx)**2+(ny-heady)**2 <= (12.0**2) and abs(nz-headz)<=12.0:
            player_hp -= 25; print("[HIT BY ENEMY] HEAD -25  HP:", player_hp)
        elif (nx-Px)**2+(ny-Py)**2 <= (PLAYER_RADIUS**2) and Pz <= nz <= Pz+EYE_HEIGHT:
            player_hp -= 10; print("[HIT BY ENEMY] BODY -10  HP:", player_hp)
        else:
            b["x"],b["y"],b["z"]=nx,ny,nz; alive.append(b); continue
        if player_hp <= 0 and not session_over:
            end_session("Killed by Enemies")
    E_BULLETS[:] = alive

def draw_enemy_bullets():
    if menu_active or map_overlay: return
    glColor3f(1.0,0.25,0.25)
    for b in E_BULLETS:
        glPushMatrix(); glTranslatef(b["x"],b["y"],b["z"]); glutSolidCube(8.0); glPopMatrix()

# ---------------- Player bullets & firing ----------------
def _push_killfeed(txt):
    kill_feed.append((txt, time.time()))
    if len(kill_feed)>4: kill_feed.pop(0)

def player_fire_common(now, speed):
    global shots_fired
    shots_fired += 1
    print(f"[SHOT] #{shots_fired} ({weapon})")
    mx,my,mz=muzzle_world_pos()
    fx=math.cos(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fy=math.sin(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fz=math.sin(math.radians(Pitch))
    bullets.append({"x":mx,"y":my,"z":mz,"vx":fx*speed,"vy":fy*speed,"vz":fz*speed,"born":now,"hit":False})

def fire_awp(now):
    global _last_shot
    if now-_last_shot<AWP_CD: return
    _last_shot=now
    player_fire_common(now, AWP_SPEED)

def apply_ak_recoil():
    global Pitch, Pangle
    Pitch = clamp(Pitch - 0.9, -60, 60)   # kick up
    Pangle = (Pangle + random.uniform(-0.6,0.6)) % 360

def fire_ak(now):
    global ak_next_fire, ak_burst_left
    if ak_mode=="single":
        if now<ak_next_fire: return
        ak_next_fire = now + AK_CD_SINGLE
        player_fire_common(now, AK_SPEED); apply_ak_recoil()
    elif ak_mode=="burst":
        if now<ak_next_fire: return
        ak_next_fire = now + AK_CD_SINGLE*1.5
        ak_burst_left = 2  # we fire once now and queue 2 more
        player_fire_common(now, AK_SPEED); apply_ak_recoil()
    elif ak_mode=="auto":
        if now<ak_next_fire: return
        ak_next_fire = now + AK_CD_AUTO
        player_fire_common(now, AK_SPEED); apply_ak_recoil()

def step_ak_burst(now):
    global ak_burst_left, ak_next_fire
    if ak_burst_left>0 and now>=ak_next_fire-AK_CD_SINGLE*1.5 + AK_BURST_SPACING*(3-ak_burst_left):
        # schedule spaced burst (poor-man's timer)
        player_fire_common(now, AK_SPEED); apply_ak_recoil()
        ak_burst_left -= 1

def step_bullets(dt,now):
    global enemies, headshots, bodykills, missed_shots, wallbang_kills, player_hp, hs_for_heal
    alive=[]
    for b in bullets:
        nx=b["x"]+b["vx"]*dt; ny=b["y"]+b["vy"]*dt; nz=b["z"]+b["vz"]*dt
        expired = (now-b["born"])>B_LIFE or abs(nx)>grid_l or abs(ny)>grid_l
        if expired and not b["hit"]:
            missed_shots+=1; print("[MISS] total=", missed_shots); continue
        elif expired: continue
        hit=False
        for e in list(enemies):
            hx,hy,hz=e["x"],e["y"],e["z"]+LEG_H+BODY_H+HEAD_R
            wb = (not has_line_of_sight(Px,Py,e["x"],e["y"]))
            if (nx-hx)**2+(ny-hy)**2<=HEAD_R**2 and abs(nz-hz)<=HEAD_R:
                e["hp"]=0; headshots+=1; hs_for_heal+=1; hit=True; b["hit"]=True
                if player_hp<100 and hs_for_heal>=2:
                    player_hp = min(100, player_hp+10); hs_for_heal-=2; print("[HEAL] +10 HP ->", player_hp)
                if wb: wallbang_kills+=1
                txt = "WALLBANG HEADSHOT" if wb else "HEADSHOT"
                print("[KILL]", txt); _push_killfeed(txt)
            elif (nx-e["x"])**2+(ny-e["y"])**2<=ENEMY_RADIUS**2 and e["z"]<=nz<=e["z"]+LEG_H+BODY_H:
                e["hp"]-=1; hit=True
                if e["hp"]<=0:
                    bodykills+=1
                    if wb: wallbang_kills+=1
                    txt = "WALLBANG BODY" if wb else "BODY"
                    print("[KILL]", txt); _push_killfeed(txt)
            if e["hp"]<=0:
                enemies.remove(e); enemies.append(spawn_enemy())
        if hit: continue
        b["x"],b["y"],b["z"]=nx,ny,nz; alive.append(b)
    bullets[:]=alive

def draw_bullets():
    if menu_active or map_overlay: return
    glColor3f(0.95,0.85,0.10)
    for b in bullets:
        glPushMatrix(); glTranslatef(b["x"],b["y"],b["z"]); glutSolidCube(B_SIZE); glPopMatrix()

# ---------------- Grenades / Smoke ----------------
SMOKES = SMOKES
def throw_grenade(type_):
    mx,my,mz=muzzle_world_pos()
    fx=math.cos(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fy=math.sin(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fz=math.sin(math.radians(Pitch))
    speed=700.0 if type_=="frag" else 600.0
    grenades.append({"x":mx,"y":my,"z":mz,"vx":fx*speed,"vy":fy*speed,"vz":fz*speed+200.0,
                     "born":time.time(),"bounces":0,"type":type_,"exploded":False})

def _process_frag_explosion(x,y,z, now):
    global enemies, grenade_kills
    killed = 0
    for e in list(enemies):
        dx,dy = e["x"]-x, e["y"]-y
        if dx*dx + dy*dy <= FRAG_RADIUS*FRAG_RADIUS:
            enemies.remove(e); enemies.append(spawn_enemy())
            grenade_kills += 1; killed += 1
            _push_killfeed("GRENADE"); print("[KILL] GRENADE")
    if killed: print(f"[GRENADE] Blast kills: {killed}")
    return killed

def step_grenades(dt,now):
    alive=[]
    for g in grenades:
        if g["exploded"]: continue
        nx,ny,nz=g["x"]+g["vx"]*dt, g["y"]+g["vy"]*dt, g["z"]+g["vz"]*dt
        g["vz"]+=GRAVITY*dt
        if abs(nx)>grid_l: g["vx"]*=-0.6; nx=clamp(nx,-grid_l,grid_l)
        if abs(ny)>grid_l: g["vy"]*=-0.6; ny=clamp(ny,-grid_l,grid_l)
        if nz<=0.0: nz=0.0; g["vz"]*=-0.35; g["vx"]*=0.85; g["vy"]*=0.85; g["bounces"]+=1
        if point_in_obstacle(nx,ny): g["vx"]*=-0.5; g["vy"]*=-0.5
        g["x"],g["y"],g["z"]=nx,ny,nz
        if (now-g["born"]>= (2.0 if g["type"]=="frag" else 1.2)) or g["bounces"]>=3:
            if g["type"]=="frag":
                explosions.append({"x":nx,"y":ny,"z":nz,"start":now})
                if (Px-nx)**2+(Py-ny)**2 <= FRAG_RADIUS**2:
                    end_session("Grenade Suicide")
                _process_frag_explosion(nx,ny,nz, now)
            else:
                SMOKES.append({"x":nx,"y":ny,"z":nz,"vx":g["vx"]*0.2,"vy":g["vy"]*0.2,"vz":max(0.0,g["vz"]*0.2),
                               "emit_end":now+SMOKE_EMIT_TIME,"puffs":[], "dead":False})
            g["exploded"]=True
        else:
            alive.append(g)
    grenades[:] = alive

def step_smokes(dt, now):
    alive_emitters=[]
    for s in SMOKES:
        if not s["dead"]:
            s["vz"] += GRAVITY*dt
            s["x"]  += s["vx"]*dt
            s["y"]  += s["vy"]*dt
            s["z"]  += s["vz"]*dt
            if s["z"] <= 0.0:
                s["z"]=0.0; s["vz"]*=-0.25; s["vx"]*=0.8; s["vy"]*=0.8
                if abs(s["vz"])<20.0: s["vz"]=0.0
            if point_in_obstacle(s["x"],s["y"]):
                s["vx"]*=-0.5; s["vy"]*=-0.5
        if now <= s["emit_end"]:
            for _ in range(SMOKE_BURST_RATE):
                s["puffs"].append(Puff(s["x"]+random.uniform(-14,14),
                                       s["y"]+random.uniform(-14,14),
                                       s["z"]+10))
        alive=[]
        for p in s["puffs"]:
            age = now - p.born
            if age > SMOKE_PUFF_LIFE: continue
            p.x += p.vx*dt*0.45; p.y += p.vy*dt*0.45; p.z += p.vz*dt*0.45
            p.vx *= 0.985; p.vy *= 0.985; p.vz *= 0.985
            if p.z > 220.0: p.vz *= 0.6
            alive.append(p)
        s["puffs"] = alive
        if now > s["emit_end"] and not s["puffs"]:
            s["dead"]=True
        if not s["dead"]:
            alive_emitters.append(s)
    SMOKES[:] = alive_emitters

def draw_grenades_and_smoke(now):
    if not menu_active and not map_overlay:
        for g in grenades:
            glPushMatrix(); glTranslatef(g["x"],g["y"],g["z"])
            glColor3f(0.3,0.3,0.3) if g["type"]=="frag" else glColor3f(0.6,0.6,0.6)
            glutSolidCube(16.0); glPopMatrix()
        new_ex=[]
        for e in explosions:
            t = now - e["start"]
            if t <= 0.6:
                r=40+t*240; glPushMatrix(); glTranslatef(e["x"],e["y"],e["z"]+10)
                glColor3f(0.95,0.55,0.10); glutWireSphere(r,10,6); glPopMatrix()
                new_ex.append(e)
        explosions[:] = new_ex
    glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDisable(GL_DEPTH_TEST)
    for s in SMOKES:
        for p in s["puffs"]:
            age = now - p.born; life_pct = clamp(age/SMOKE_PUFF_LIFE, 0.0, 1.0)
            alpha = 0.65*(1.0-life_pct) + 0.15
            glColor4f(0.82,0.82,0.82, alpha)
            glPushMatrix(); glTranslatef(p.x,p.y,p.z); glutSolidSphere(SMOKE_PUFF_SIZE, 12, 10); glPopMatrix()
    glEnable(GL_DEPTH_TEST); glDisable(GL_BLEND)

# ---------------- HUD / Menus / Map ----------------
def draw_floor():
    step=120
    for x in range(-grid_l,grid_l,step):
        for y in range(-grid_l,grid_l,step):
            glColor3f(0.18,0.18,0.22) if ((x//step+y//step)&1)==0 else glColor3f(0.14,0.14,0.17)
            glBegin(GL_QUADS); glVertex3f(x,y,0); glVertex3f(x+step,y,0); glVertex3f(x+step,y+step,0); glVertex3f(x,y+step,0); glEnd()

def draw_boxes(objs,color=(0.40,0.42,0.48)):
    glColor3f(*color)
    for (cx,cy,sx,sy,h) in objs:
        glPushMatrix(); glTranslatef(cx,cy,h*0.5); glScalef(sx*2,sy*2,h); glutSolidCube(1.0); glPopMatrix()

def draw_text(x,y,s,font=GLUT_BITMAP_HELVETICA_18):
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0,win_w,0,win_h)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glColor3f(1,1,1); glRasterPos2f(x,y)
    for ch in s: glutBitmapCharacter(font, ord(ch))
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)

def format_time(secs):
    m=int(secs//60); s=int(secs%60); return f"{m:02d}:{s:02d}"

def draw_health_bar():
    if menu_active or map_overlay: return
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0,win_w,0,win_h)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    # background 200px
    glColor3f(0.25,0.25,0.25); glBegin(GL_QUADS)
    glVertex2f(12,28); glVertex2f(212,28); glVertex2f(212,48); glVertex2f(12,48); glEnd()
    w = 2*player_hp  # 0..200
    glColor3f(0.15,0.8,0.2) if player_hp>35 else glColor3f(0.9,0.2,0.1)
    glBegin(GL_QUADS); glVertex2f(12,28); glVertex2f(12+w,28); glVertex2f(12+w,48); glVertex2f(12,48); glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)

def draw_crosshair():
    if not crosshair_on or (weapon=="AWP" and scope_on) or menu_active or map_overlay: return
    cx,cy=win_w//2, win_h//2
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0,win_w,0,win_h)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glColor3f(1,1,1); glBegin(GL_LINES)
    glVertex2f(cx-10,cy); glVertex2f(cx-2,cy); glVertex2f(cx+2,cy); glVertex2f(cx+10,cy)
    glVertex2f(cx,cy-10); glVertex2f(cx,cy-2); glVertex2f(cx,cy+2); glVertex2f(cx,cy+10)
    glEnd(); glPointSize(4); glBegin(GL_POINTS); glVertex2f(cx,cy); glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)

def draw_scope_overlay():
    if weapon!="AWP" or not scope_on or menu_active or map_overlay: return
    cx,cy=win_w//2,win_h//2; r=int(min(win_w,win_h)*0.42)
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0,win_w,0,win_h)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glColor3f(0,0,0)
    glBegin(GL_QUADS); glVertex2f(0,0); glVertex2f(cx-r,0); glVertex2f(cx-r,win_h); glVertex2f(0,win_h); glEnd()
    glBegin(GL_QUADS); glVertex2f(cx+r,0); glVertex2f(win_w,0); glVertex2f(win_w,win_h); glVertex2f(cx+r,win_h); glEnd()
    glBegin(GL_QUADS); glVertex2f(cx-r,cy+r); glVertex2f(cx+r,cy+r); glVertex2f(cx+r,win_h); glVertex2f(cx-r,win_h); glEnd()
    glBegin(GL_QUADS); glVertex2f(cx-r,0); glVertex2f(cx+r,0); glVertex2f(cx+r,cy-r); glVertex2f(cx-r,cy-r); glEnd()
    glColor3f(0,0,0); glLineWidth(3); glBegin(GL_LINE_LOOP)
    for i in range(120):
        t=2*math.pi*i/120.0; glVertex2f(cx+r*math.cos(t), cy+r*math.sin(t))
    glEnd()
    glLineWidth(2); glBegin(GL_LINES); glVertex2f(cx-r,cy); glVertex2f(cx+r,cy); glEnd()
    glBegin(GL_LINES); glVertex2f(cx,cy-r); glVertex2f(cx,cy+r); glEnd()
    glColor3f(1,0,0); glPointSize(5); glBegin(GL_POINTS); glVertex2f(cx,cy); glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)

def draw_hud():
    if menu_active or map_overlay: return
    wep = f"{weapon} ({ak_mode})" if weapon=="AK" else "AWP"
    draw_text(10, win_h-20, f"{wep} | Kills:{headshots+bodykills+grenade_kills} (H:{headshots} B:{bodykills} N:{grenade_kills})  WB:{wallbang_kills}  Time:{format_time(play_time)}")
    draw_text(10, win_h-40, f"Shots:{shots_fired}  Missed:{missed_shots}")
    draw_text(10, 10, "V:Swap  RMB:Scope/Mode  LMB:Fire  X:Map  Z:Zoom(AWP)  G:Frag  T:Smoke  E:Crosshair  C:Xray  Q:End  Esc:Menu")
    draw_health_bar()

def draw_full_map_overlay():
    if not map_overlay or menu_active: return
    road=(0.76,0.64,0.48); walls=(0.28,0.30,0.34); border=(0.10,0.10,0.10)
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(-grid_l, grid_l, -grid_l, grid_l)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glColor3f(*road); glBegin(GL_QUADS)
    glVertex2f(-grid_l,-grid_l); glVertex2f(grid_l,-grid_l); glVertex2f(grid_l,grid_l); glVertex2f(-grid_l,grid_l); glEnd()
    glColor3f(*walls)
    for (cx,cy,sx,sy,h) in MAZE+CRATES:
        glBegin(GL_QUADS); glVertex2f(cx-sx, cy-sy); glVertex2f(cx+sx, cy-sy); glVertex2f(cx+sx, cy+sy); glVertex2f(cx-sx, cy+sy); glEnd()
    glColor3f(*border); glLineWidth(3.0); glBegin(GL_LINE_LOOP)
    glVertex2f(-grid_l,-grid_l); glVertex2f(grid_l,-grid_l); glVertex2f(grid_l,grid_l); glVertex2f(-grid_l,grid_l); glEnd()
    glPointSize(10.0); glColor3f(1.0,0.15,0.15); glBegin(GL_POINTS); glVertex2f(Px,Py); glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)

# Menus
def current_menu_items(): return ["Restart","Exit"] if session_over else ["Continue","End Session","Restart","Exit"]

def draw_menu():
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0,win_w,0,win_h)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(0,0,0,0.45); glBegin(GL_QUADS); glVertex2f(0,0); glVertex2f(win_w,0); glVertex2f(win_w,win_h); glVertex2f(0,win_h); glEnd()
    glDisable(GL_BLEND)
    title = "== TRAINING SESSION END ==" if session_over else "== GAME PAUSED =="
    draw_text(win_w//2-160, win_h-90, title)
    items=current_menu_items(); global menu_click_zones; menu_click_zones=[]
    for i,item in enumerate(items):
        prefix="> " if i==menu_choice else "  "; y=win_h-160-44*i
        draw_text(win_w//2-80, y, prefix+item)
        menu_click_zones.append((win_w//2-100, y-14, win_w//2+100, y+14, item))
    if session_over:
        draw_text(win_w//2-220, win_h//2,   f"Kills:{headshots+bodykills+grenade_kills} (H:{headshots} B:{bodykills} N:{grenade_kills})  WB:{wallbang_kills}")
        draw_text(win_w//2-220, win_h//2-30,f"Shots:{shots_fired}  Miss:{missed_shots}  Time:{format_time(play_time)}")
        draw_text(win_w//2-220, win_h//2-60,f"Reason: {session_reason}")
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)

# ---------------- Display / Loop ----------------
prev_time=None
def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glEnable(GL_DEPTH_TEST)
    setupCamera()
    # world always behind overlays
    draw_floor(); draw_boxes(MAZE,(0.40,0.42,0.48)); draw_boxes(CRATES,(0.32,0.34,0.40))
    for e in enemies: draw_enemy(e)
    if xray:
        glDisable(GL_DEPTH_TEST)
        for e in enemies: draw_enemy(e,(1.0,0.2,0.7))
        glEnable(GL_DEPTH_TEST)
    draw_bullets(); draw_enemy_bullets()
    now=time.time(); draw_grenades_and_smoke(now)
    draw_weapon(); draw_scope_overlay(); draw_crosshair(); draw_hud(); draw_full_map_overlay()
    if menu_active: draw_menu()
    glutSwapBuffers()

def reshape(w,h):
    global win_w,win_h,aspect
    if h==0: h=1
    win_w,win_h=w,h; aspect=w/float(h); glViewport(0,0,w,h)

def idle():
    global prev_time, Px, Py, Pz, Pvz, play_time, ak_burst_left
    now=time.time()
    if prev_time is None: prev_time=now
    dt=now-prev_time; prev_time=now
    if not menu_active and not session_over and not map_overlay:
        play_time += dt

    if menu_active:
        glutPostRedisplay(); return

    # jump physics
    Pvz += GRAVITY_PLAYER*dt; Pz += Pvz*dt
    if Pz <= GROUND_EPS:
        Pz=0.0; 
        if Pvz<0: Pvz=0.0

    if not session_over and not map_overlay:
        fwdx=math.cos(math.radians(Pangle))*math.cos(math.radians(Pitch))
        fwdy=math.sin(math.radians(Pangle))*math.cos(math.radians(Pitch))
        step=Pspeed*dt
        if key_W:
            nx,ny=Px+fwdx*step, Py+fwdy*step
            if not blocked(nx,ny): Px,Py=nx,ny
        if key_S:
            nx,ny=Px-fwdx*step, Py-fwdy*step
            if not blocked(nx,ny): Px,Py=nx,ny
        if key_A: globals()["Pangle"]=(Pangle+120*dt)%360
        if key_D: globals()["Pangle"]=(Pangle-120*dt)%360

        update_enemies(dt)
        step_bullets(dt,now)
        step_enemy_bullets(dt)

        # weapon continuous logic
        if weapon=="AK":
            if mouse_left_down: fire_ak(now)
            if ak_mode=="burst" and ak_burst_left>0:
                step_ak_burst(now)

    step_grenades(dt,now); step_smokes(dt,now); enemy_try_fire(now)
    glutPostRedisplay()

# ---------------- Input ----------------
def keyDown(k,x,y):
    global key_W,key_S,key_A,key_D, xray, zoomed, map_overlay, menu_active, menu_choice, crosshair_on, Pvz, weapon, ak_mode, scope_on
    if k in (b'w',b'W'): key_W=True
    elif k in (b's',b'S'): key_S=True
    elif k in (b'a',b'A'): key_A=True
    elif k in (b'd',b'D'): key_D=True
    elif k in (b'c',b'C'): xray=not xray
    elif k in (b'z',b'Z'): 
        if weapon=="AWP": zoomed=not zoomed
    elif k in (b'g',b'G'): throw_grenade("frag")
    elif k in (b't',b'T'): throw_grenade("smoke")
    elif k in (b'x',b'X'): map_overlay = not map_overlay
    elif k in (b'e',b'E'): crosshair_on = not crosshair_on
    elif k in (b'v',b'V'):
        weapon = "AWP" if weapon=="AK" else "AK"
        scope_on=False; zoomed=False
        # default crosshair behavior
        crosshair_on = (weapon=="AK")
        print("[WEAPON]", weapon)
    elif k in (b' ',):     
        if Pz <= GROUND_EPS and Pvz == 0.0: Pvz = JUMP_V0
    elif k in (b'q',b'Q'): end_session("Quit")
    elif k in (b'\x1b',):  # Esc
        menu_active = not menu_active; menu_choice = 0
    elif k in (b'\r', b'\n'):
        if menu_active:
            label = current_menu_items()[menu_choice]; menu_activate(label)

def keyUp(k,x,y):
    global key_W,key_S,key_A,key_D
    if k in (b'w',b'W'): key_W=False
    elif k in (b's',b'S'): key_S=False
    elif k in (b'a',b'A'): key_A=False
    elif k in (b'd',b'D'): key_D=False

def special(k,x,y):
    global menu_choice
    if not menu_active: return
    n=len(current_menu_items())
    if k==GLUT_KEY_UP:   menu_choice=(menu_choice-1)%n
    if k==GLUT_KEY_DOWN: menu_choice=(menu_choice+1)%n

def mouse(btn,state,x,y):
    global scope_on, mouse_left_down, ak_mode
    if btn==GLUT_LEFT_BUTTON:
        mouse_left_down = (state==GLUT_DOWN)
        if state==GLUT_DOWN:
            if weapon=="AWP": fire_awp(time.time())
            # AK handled continuously in idle
    elif btn==GLUT_RIGHT_BUTTON and state==GLUT_DOWN and not menu_active and not map_overlay:
        if weapon=="AK":
            ak_mode = {"single":"burst","burst":"auto","auto":"single"}[ak_mode]
            print("[AK MODE]", ak_mode)
        else:
            scope_on = not scope_on
    if state==GLUT_DOWN and menu_active:
        yy = win_h - y
        for (x0,y0,x1,y1,label) in menu_click_zones:
            if x0<=x<=x1 and y0<=yy<=y1: menu_activate(label); break

def mouseMotion(x,y):
    global Pangle,Pitch
    if menu_active or map_overlay: return
    cx,cy=win_w//2,win_h//2
    dx,dy=x-cx,y-cy
    sens=0.2
    Pangle=(Pangle - dx*sens) % 360
    Pitch =clamp(Pitch - dy*sens, -60.0, 60.0)
    glutWarpPointer(cx,cy)

# ---------------- Menus / End / Exit ----------------
def quit_game():
    print("[SESSION] Exit")
    try: glutLeaveMainLoop()
    except Exception: pass
    try:
        w=glutGetWindow()
        if w: glutDestroyWindow(w)
    except Exception: pass
    try: sys.exit(0)
    except SystemExit: pass
    os._exit(0)

def menu_activate(label):
    global menu_active, headshots, bodykills, shots_fired, missed_shots, wallbang_kills, grenade_kills
    global Px,Py,Pz,Pangle,Pitch, bullets, grenades, explosions, SMOKES
    global zoomed, scope_on, xray, session_over, player_hp, E_BULLETS, kill_feed, Pvz, map_overlay, play_time
    global weapon, ak_mode, hs_for_heal
    if label=="Continue" and not session_over:
        menu_active=False
    elif label=="End Session" and not session_over:
        end_session("Ended from Menu")
    elif label=="Restart":
        headshots=bodykills=shots_fired=missed_shots=wallbang_kills=grenade_kills=0; hs_for_heal=0
        bullets.clear(); grenades.clear(); explosions.clear(); SMOKES.clear(); E_BULLETS.clear(); kill_feed.clear()
        reset_enemies()
        Px,Py,Pz,Pangle,Pitch,Pvz = 0.0,-900.0,0.0,90.0,0.0,0.0
        zoomed=scope_on=xray=False
        session_over=False; menu_active=False; map_overlay=False
        player_hp=100; play_time=0.0
        weapon="AK"; ak_mode="single"; print("[SESSION] Restarted")
        crosshair_on=True
    elif label=="Exit":
        quit_game()

def end_session(reason):
    global session_over, menu_active, session_reason, map_overlay
    if session_over: return
    session_over=True; menu_active=True; map_overlay=False
    session_reason = reason
    print("Training Session End")
    print(f"Reason: {session_reason}")
    print(f"Time: {format_time(play_time)} | "
          f"Kills:{headshots+bodykills+grenade_kills} (H:{headshots} B:{bodykills} N:{grenade_kills}) | "
          f"Shots:{shots_fired} Miss:{missed_shots} | WB:{wallbang_kills}")

# ---------------- Main ----------------
def main():
    random.seed(21); reset_enemies()
    glutInit(); glutInitDisplayMode(GLUT_DOUBLE|GLUT_RGB|GLUT_DEPTH)
    glutInitWindowSize(win_w,win_h); glutInitWindowPosition(60,40)
    glutCreateWindow(b"Shooting-Arena 2.0 by Ohi")
    try: glutSetCursor(GLUT_CURSOR_NONE)
    except Exception: pass
    glutDisplayFunc(display); glutReshapeFunc(reshape); glutIdleFunc(idle)
    glutKeyboardFunc(keyDown); glutKeyboardUpFunc(keyUp)
    glutSpecialFunc(special); glutMouseFunc(mouse); glutPassiveMotionFunc(mouseMotion)
    glutWarpPointer(win_w//2,win_h//2)
    glutMainLoop()

if __name__=="__main__":
    main()
