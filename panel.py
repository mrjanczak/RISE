#! /usr/bin/env python

# Script draws engine panel from 737 MAX
# Required pygame and PibotoCondensed font
# Control by mouse and keyboard
# (C) Michal Janczak, Poland 2024

# 0. Prepare Raspberry Pi image Raspberry Pi OS with desktop (64-bit)
# 1. Install:
#      sudo apt install python3-build-hat
#      sudo apt install python3-rpi.gpio -y
# 2. Enable Serial port in Raspberry:

    # Open your terminal on the Pi or via SSH and type: sudo raspi-config
    # Navigate to Interface Options (or Interfacing Options) and select Serial Port.
    # Answer No to the prompt: "Would you like a login shell to be accessible over serial?"
    # Answer Yes to the prompt: "Would you like the serial port hardware to be enabled?"
    # Select Finish and choose Yes to reboot your Raspberry Pi

# 3. In admin/ folder run `git clone https://github.com/mrjanczak/RAISE.git`
# 4. Run sudo nano /etc/xdg/autostart/display.desktop and paste:
#    [Desktop Entry]
#    Name=RisePanel
#    Exec=/usr/bin/python3 /home/rise/RISE/panel.py
# 5. Reboot

from time import sleep
print('RISE control panel initiation...')
sleep(1)

import math
import numpy as np
import pygame
import pygame.gfxdraw
from datetime import datetime

import threading
import RPi.GPIO as GPIO
import time
from hr8825 import HR8825 as H

SPEED_MULT = 1
verbose = False

locked = True
pin = '7473'

class Motor():
    def __init__(self, port):
        pass
    def start(self, speed):
        pass
    def stop(self):
        pass  
    def run_for_degrees(self, degrees):
        pass

# Initiate servos
# from buildhat import Motor
motors = [Motor('A') , Motor('B'), Motor('C'), Motor('D')]


# Motors
PUMP_MOTOR = 0
OGV_MOTOR = 1
N1_MOTOR = 2
N2_MOTOR = 3

# Default detent values
N1, GI_N1, REV_N1, CRZ_N1, CL_N1, TOGA_N1, N1_MAX, N1_STEP = 0.0, 20.0, 60.0, 90.0, 95.0, 100., 100., 10
EGT = 0.0
N2, N2_MAX, N2_STEP = 0.0, 100., 10.
FF, FF_MAX, FF_STEP = 0.0, 100., 10.  # fuel flow    []
OP = 60 # oil pressure []
OT = 70 # oil temp     []
OQ = 90 # oil quantity []
VIB = 0.0 # vibrations [CU]

PCM, PCM_MAX, PCM_STEP = 30., 30., 10.
OGV, OGV_MAX, OGV_STEP = 30., 30., 10.
VBV, VBV_MAX, VBV_STEP = 0.0, 30., 10.
VSV, VSV_MAX, VSV_STEP = 0.0, 30., 10.
ACC, ACC_MAX, ACC_STEP = 0.0, 30., 10.
TAT = 20

# Init stepper motors
def control_stepper(id, speed):
    name = threading.current_thread().name
    print(f'Init {name}')
    if name == 'Motor1':
        Motor = H(dir_pin=13, step_pin=19, enable_pin=12, mode_pins=(16, 17, 20))
        
    while True:
        speed_ = int(speed())
        if speed_ > 0:
            stepdelay = 1/(speed_*SPEED_MULT)
            Motor.TurnStep(Dir='forward', steps=speed_, stepdelay = stepdelay)
        elif speed() < 0:
            stepdelay = abs(1/(speed()*SPEED_MULT))
            Motor.TurnStep(Dir='backward', steps=speed_, stepdelay = stepdelay)            
        else:
            Motor.Stop()
            time.sleep(.1)

Motor1 = threading.Thread(target = control_stepper, name = 'Motor1', args = (id, lambda: N1 ))
Motor1.start()

# Init LEGO servos
motors = [Motor('A') , Motor('B'),  Motor('C'), Motor('D')]
ratios = [1, 24*20/12, 1, 1]
direction = [1,1,-1,1]
step = [0,360*2,0,0]

speed_max = [100,50,50,50]
speed_min = [20,20,20,20]
time_sec = 60
deg = 360*20

# Valves
PCLM = False
FPAS = False

VBV = False
VSV = False
ACCR = False
ACCS = False

def start_stop_motor(motor_i, speed):
    if speed:
        if abs(speed) < speed_min[motor_i]:
            speed = np.sign(speed)*speed_min[motor_i]
        if abs(speed) > speed_max[motor_i]:
            speed = np.sign(speed)*speed_max[motor_i]
        motors[motor_i].start(speed = speed*direction[motor_i])

    else:
        motors[motor_i].stop()

def rotate_motor(motor_i, degrees):
    motors[motor_i].run_for_degrees(degrees = degrees)

def stop_all():
    for motor in motors:
        motor.stop()

width = 1024
height = 580
caption = "RISE Engine Panel"
running = True
dt = 0.0

pygame.init()
screen = pygame.display.set_mode((width, height))
pygame.display.set_caption(caption)
clock = pygame.time.Clock()

# colors
black = (0,0,0)
white = (255, 255, 255)
gray = (145, 146, 150)
red = (235, 50, 40)
yellow = (247,173,1)
blue = (0,255,255)
green = (0,255,0)
rad = math.pi/180
font1 = 'PibotoCondensed' # RasPi
# font1 = 'RobotoCondensed' # Windows

pin_ = ''
header_msg = 'Panel locked'
click_rects = {}
timer = datetime.now()
det_lab, det_N1 = '', ''

# Definition of panels; NOR/LIM/ULT tuplets define arc range, values in [] are shown as yellow/red markers
panels = [[
            {'title':'N1',         'type':'gauge', 'scale':.5,   'NOR':(0, 91),  'LIM':([-92], 103), 'ULT':[105], 'prec':1, 'keys':[pygame.K_1, pygame.K_q], 'div':(20,2)},
            {'title':'EGT',        'type':'gauge', 'scale':4.5,  'NOR':(0, 920), 'LIM':[930],        'ULT':[950], 'prec':1},
            {'title':'N2',         'type':'gauge', 'scale':.555, 'NOR':(0, 115), 'ULT':[117],                     'prec':1, 'keys':[pygame.K_2, pygame.K_w]},
        ],[
            {'title':'FF',         'type':'value', 'scale':1.,   'prec':0},
            {'title':'OIL/PRESS',  'type':'level', 'scale':1.55, 'ULT':[1],      'LIM':(5, [25]), 'NOR':(29, 125) },
            {'title':'OIL/TEMP',   'type':'level', 'scale':1.6,  'NOR':(0, 110), 'LIM':[114] ,    'ULT':[126] },
            {'title':'OIL/QTY %',  'type':'value', 'scale':1.,   'prec':0 },
            {'title':'VIB',        'type':'level', 'scale':0.065,'NOR':(0, 3.8), 'LIM':([4], 5), 'prec':1},
        ],[
            {'title':'PCM %',      'type':'level', 'scale':0.75, 'LIM':(-PCM_MAX,[-2]), 'NOR':(0, PCM_MAX), 'offset': PCM_MAX, 'keys':[pygame.K_5, pygame.K_t]},
            {'title':'OGV %',      'type':'level', 'scale':0.75, 'NOR':(-OGV_MAX, OGV_MAX),                 'offset': OGV_MAX, 'keys':[pygame.K_4, pygame.K_r]},
            {'title':'VBV %',      'type':'level', 'scale':0.75, 'NOR':(-VBV_MAX, VBV_MAX),                 'offset': VBV_MAX, 'keys':[pygame.K_6, pygame.K_y]},
            {'title':'VSV %',      'type':'level', 'scale':0.75, 'NOR':(-VSV_MAX, VSV_MAX),                 'offset': VSV_MAX, 'keys':[pygame.K_7, pygame.K_u]},
            {'title':'ACC %',      'type':'level', 'scale':0.75, 'NOR':(-ACC_MAX, ACC_MAX),                 'offset': ACC_MAX, 'keys':[pygame.K_8, pygame.K_i]},
        ],[
            {'type':'buttons', 'buttons':['STOP', 'L'],  'keys':[pygame.K_s, pygame.K_l]},
            {},
            {'type':'buttons', 'buttons':['1', '2', '3'], 'keys':[pygame.K_1, pygame.K_2, pygame.K_3], 'in_locked':True},
            {'type':'buttons', 'buttons':['4', '5', '6'], 'keys':[pygame.K_4, pygame.K_5, pygame.K_6], 'in_locked':True},
            {'type':'buttons', 'buttons':['7', '8', '9'], 'keys':[pygame.K_7, pygame.K_8, pygame.K_9], 'in_locked':True},
            {'type':'buttons', 'buttons':['0', 'ENTER'],  'keys':[pygame.K_0, pygame.K_RETURN],        'in_locked':True},
        ]]

def draw():
    global values, click_rects, locked, header_msg

    screen.fill(black)

    # Dummy logic of params based on N1
    EGT = np.interp(N1,[0,20,60,90,100] ,[0,200,600,800,900])
    N2 = np.interp(N1,[0,20,60,90,100]  ,[0,60,80,95,100])
    FF = np.interp(N1,[0,20,60,90,100]  ,[0,20,50,70,100])
    VIB = np.interp(N1,[0,20,60,90,100] ,[0,0.1,0.3,0.45,0.5])

    values = [[N1, EGT, N2,], [FF, OP, OT, OQ, VIB], [PCM, OGV, VBV, VSV, ACC], [0]*len(panels[3]) ]
    click_rects = {}

    # Show header
    if locked:
        color = red
    else:
        color = green

    y0 = 25
    for text, x0, size, color in [('TAT', 20, 15, blue), (f'{TAT}C', 50, 20, white), (header_msg, 90, 20, color)]:
        font = pygame.font.SysFont(font1,size, bold = True)
        text = font.render(str(text), True, color, black)
        rect = text.get_rect()
        rect.bottomleft = (x0, y0 )
        screen.blit(text, rect)

    for col in range(0,len(panels)):
        x0, y0, dy = 20 + col*260, 30, 5

        for value, panel in zip(values[col], panels[col]):
            y0 += dy

            type_ = panel.get('type', 'separator')
            scale = panel.get('scale',1.0)
            title = panel.get('title',False)
            prec = panel.get('prec',0)
            offset = panel.get('offset', 0)
            keys = panel.get('keys', [])
            in_locked = panel.get('in_locked', False)
            value = round(value, prec)

            # Basic dimensions
            if type_ == 'gauge':
                w0, h0, r0 = 200, 150, 65
                y0 += h0
                xt, yt = x0 + w0, y0 - 10 # title center
                xc, yc = x0 + int(w0/2), y0 - r0 # circle center
                wb, hb, thc, vsize = 95, 40,  2, 35
                xb, yb = xc, yc - hb - 10  # value border

                if not locked and len(keys)==2:
                    click_rects[keys[0]] = pygame.Rect(x0,     y0-h0,w0/2-1,h0)
                    click_rects[keys[1]] = pygame.Rect(x0+w0/2,y0-h0,w0/2,  h0)

            elif type_ == 'value':
                w0, h0 = 200, 75
                y0 += h0
                xt, yt = x0 + w0, y0 - int(h0/2) # title center
                wb, hb, thc, vsize = 75, 40,  2, 35
                xb, yb   = x0 + 40, yt - int((hb)/2)  # value border

            elif type_ == 'level':
                w0, h0 = 200, 100
                y0 += h0
                xt, yt = x0 + w0, y0 - int(h0/2) # title center
                wb, hb, thc, vsize = 60, 30, 2, 25
                xb, yb  = x0 + 40, yt - int((hb)/2)  # value border
                xc, yc = xb + wb + 20, y0 - 10

                if not locked and len(keys)==2:
                    click_rects[keys[0]] = pygame.Rect(x0,y0-h0,  w0,h0/2-1)
                    click_rects[keys[1]] = pygame.Rect(x0,y0-h0/2,w0,h0/2)

            elif type_ == 'buttons':
                w0, h0 = 200, 60
                y0 += h0
                wb, hb, thc, bsize = 50, 50, 2, 35

            elif type_ == 'separator':
                y0 += 100

            # pygame.draw.rect(screen, red, [x0, y0-h0, w0, h0], width = 1)

            # title
            if title:
                tsize = 20
                if '/' in title:
                    yt -= int(tsize/2)

                line = -1
                for txt in title.split('/'):
                    line += 1
                    if line > 0:
                        yt += tsize + 1

                    font = pygame.font.SysFont(font1,tsize, bold = True)
                    text = font.render(txt, True, blue, black)
                    rect = text.get_rect()
                    rect.center = (xt, yt)
                    screen.blit(text, rect)

            # value with border
            if type_ in ['gauge','value','level']:
                pygame.draw.rect(screen, white, [xb, yb, wb, hb], width = thc)
                font = pygame.font.SysFont(font1,vsize, bold = True)
                text = font.render(str(value), True, white)
                rect = text.get_rect()
                rect.bottomright = (xb + wb - thc, yb + hb + 2)
                screen.blit(text, rect)

                # Autothrust Label - detent
                if title == 'N/1':
                    font = pygame.font.SysFont(font1,vsize-2, bold = True)
                    text = font.render(str(det_N1), True, green, black)
                    rect = text.get_rect()
                    rect.bottomright = (xb + w - thc-3, yb)
                    screen.blit(text, rect)

                value += offset

            # gauge arrow & sector
            if type_ == 'gauge':
                a = value/scale
                p = [(xc, yc)]
                # Draw sector
                for n in range(0, int(a)):
                    x = xc + int(r0*math.cos(n*rad))
                    y = yc+int(r0*math.sin(n*rad))
                    p.append((x, y))
                p.append((xc, yc))
                if len(p) > 2:
                    pygame.draw.polygon(screen, gray, p)

                r2 = r0 + 10
                x1, y1 = xc, yc
                x2, y2 = r2*math.cos(a*rad)+xc, r2*math.sin(a*rad) + yc
                pygame.draw.line(screen, white, [x1, y1], [x2, y2], width=3)

            # level arrow
            if type_ == 'level':
                x1, y1 = xc + 2,  yc - value/scale
                x2, y2 = x1 + 15, y1 + 4
                x3, y3 = x1 + 15, y1 - 4
                pygame.draw.polygon(screen, white, [[x1, y1], [x2, y2], [x3, y3]], width = 0 )

            # Buttons
            if type_== 'buttons':
                xb, yb = x0, y0 - h0
                for key, button in zip(panel['keys'], panel['buttons']):

                    wb_ = wb
                    if len(button) > 1:
                        wb_ = 115

                    pygame.draw.rect(screen, white, [xb, yb, wb_, hb], width = thc)

                    font = pygame.font.SysFont(font1, bsize, bold = True)
                    text = font.render(str(button), True, white)
                    rect = text.get_rect()
                    rect.center = (xb + int(wb_/2), yb + int(hb/2))
                    screen.blit(text, rect)

                    if in_locked == locked:
                        click_rects[key] = pygame.Rect(xb, yb, wb_, hb)

                    xb += wb_ + 15


            # Markers & scale divisions
            for lab in ['NOR', 'LIM', 'ULT']:
                markers = []
                rad_sign = []
                if lab not in panel:
                    continue

                # single value
                if type(panel[lab]) in [int, float]:
                    a0 = (panel[lab]+offset)/scale
                    a1 = a0

                # list with single value - marker
                elif type(panel[lab]) == list:
                    a0 = (panel[lab][0]+offset)/scale
                    a1 = a0
                    markers.append(abs(a0))
                    rad_sign.append(np.sign(a0))

                elif type(panel[lab] == tuple):
                    a0, a1 = panel[lab]

                    # first value in [] - marker
                    if type(a0) == list:
                        a0 = (a0[0]+offset)/scale
                        markers.append(abs(a0))
                        rad_sign.append(np.sign(a0))
                    else:
                        a0 = (a0+offset)/scale

                    # second value in [] - marker
                    if type(a1) == list:
                        a1 = (a1[0]+offset)/scale
                        markers.append(abs(a1))
                        rad_sign.append(np.sign(a1))
                    else:
                        a1 = (a1+offset)/scale

                if type_ == 'gauge':

                    if lab == 'NOR':
                        color, r1 = white,  r0-5
                    elif lab == 'LIM':
                        color, r1 = yellow, r0-1
                    elif lab == 'ULT':
                        color, r1 = red,    r0-1

                    # Arcs
                    da = a1 - a0
                    if da != 0:
                        pygame.gfxdraw.arc(screen, xc, yc, r0,  int(a0), int(a1), white)
                        pygame.gfxdraw.arc(screen, xc, yc, r0-1,  int(a0), int(a1), white)

                    # Markers
                    for a, sign in zip(markers, rad_sign):
                        r2 = r1+sign*10
                        x1, y1 = r1 * math.cos(a * rad) + xc, r1 * math.sin(a * rad) + yc
                        x2, y2 = r2 * math.cos(a * rad) + xc, r2 * math.sin(a * rad) + yc
                        pygame.draw.line(screen, color, [x1, y1], [x2, y2], width=2)

                    # Scale division
                    if 'div' in panel and lab == 'NOR':
                        division, modulo = panel['div']
                        for d in range(11):
                            a = d * division
                            r2 = r1 + 5
                            x1, y1 = r1 * math.cos(a * rad) + xc, r1 * math.sin(a * rad) + yc
                            x2, y2 = r2 * math.cos(a * rad) + xc, r2 * math.sin(a * rad) + yc
                            pygame.draw.line(screen, color, [x1, y1], [x2, y2], width=2)

                            if d % modulo == 0:
                                rd = r0 - 15
                                xd, yd = rd * math.cos(a * rad) + xc, rd * math.sin(a * rad) + yc
                                font = pygame.font.SysFont(font1,13, bold = True)
                                text = font.render(str(d), True, color)
                                rect = text.get_rect()
                                rect.center = (xd, yd)
                                screen.blit(text, rect)

                elif type_ == 'level':

                    if lab == 'NOR':
                        color, r1, r2 = white,  0, 5
                    elif lab == 'LIM':
                        color, r1, r2 = yellow, 0, 5
                    elif lab == 'ULT':
                        color, r1, r2 = red,   -2, 8

                    if a0 != a1:
                        x1, y1 = xc, yc - abs(a0)
                        x2, y2 = xc, yc - abs(a1)
                        pygame.draw.line(screen, color, [x1, y1], [x2, y2], width=2)

                    for a in markers:
                        x1, y1 = xc+r1, yc - abs(a)
                        x2, y2 = xc+r2, yc - abs(a)
                        pygame.draw.line(screen, color, [x1, y1], [x2, y2], width=2)

    x0, y0 = 20, height-30
    help = ["1/Q - N1; 2/W - N2, 3/E - FF, 4/R - OGV", "5/T - PCM, 6/Y - VBV, 7/U - VSV, 8/I - ACC, S - stop, L - lock"]
    for txt in help:
        font = pygame.font.SysFont(font1,15, bold = True)
        text = font.render(txt, True, white, black)
        rect = text.get_rect()
        rect.bottomleft = (x0, y0)
        screen.blit(text, rect)
        y0 += 20

    pygame.display.flip()

def control(event):
    global pin_, timer, locked, header_msg, N1, N2, OGV, FF,  PCM, VBV, VSV, ACC

    # Get pressed keys
    if event.type == pygame.KEYDOWN:
        keys = pygame.key.get_pressed()

    if event.type == pygame.MOUSEBUTTONDOWN:
        if event.button == 1:
            xm, ym = event.pos

            keys = {}
            for key in '1,2,3,4,5,6,7,8,9,0,q,w,e,r,t,y,u,i,s,l,return'.split(','):
                keys[pygame.key.key_code(key)] = False

            for key, rect in click_rects.items():
                if rect.collidepoint(xm, ym):
                    keys[key] = True

            timer = datetime.now()

    # Control
    if keys[pygame.K_s]:
        header_msg = 'All motors stopped'  
        print(header_msg)
        N1, N2, FF = 0, 0, 0
        stop_all()

    if keys[pygame.K_l]:
        print('Lock panel')
        locked = True
        header_msg = 'Panel locked'

    if locked:
        if keys[pygame.K_1]:
            pin_ += '1'
        if keys[pygame.K_2]:
            pin_ += '2'
        if keys[pygame.K_3]:
            pin_ += '3'
        if keys[pygame.K_4]:
            pin_ += '4'
        if keys[pygame.K_5]:
            pin_ += '5'
        if keys[pygame.K_6]:
            pin_ += '6'
        if keys[pygame.K_7]:
            pin_ += '7'
        if keys[pygame.K_8]:
            pin_ += '8'
        if keys[pygame.K_9]:
            pin_ += '9'
        if keys[pygame.K_0]:
            pin_ += '0'

        if keys[pygame.K_RETURN]:
            if pin_ == pin:
                locked = False    
                header_msg = 'Panel unlocked'            
                print('Password ' + '*'*len(pin_) + ' correct')
            else:
                locked = True
                header_msg = 'Password ' + '*'*len(pin_) + ' incorrect'
                print(header_msg)
            pin_ = ''

    if not locked:

        if keys[pygame.K_1]:
            N1 += N1_STEP
            header_msg = 'N1 speed increased.'
            start_stop_motor(N1_MOTOR, int(N1/N1_MAX*100))
        if keys[pygame.K_q]:
            N1 -= N1_STEP
            header_msg = 'N1 speed decreased.'
            start_stop_motor(N1_MOTOR, int(N1/N1_MAX*100))

        N1 = np.interp(N1, [0,N1_MAX], [0,N1_MAX])


        if keys[pygame.K_2]:
            N2 += N2_STEP
            header_msg = 'N2 speed increased.' 
            start_stop_motor(N2_MOTOR, int(N2/N2_MAX*100))           
        if keys[pygame.K_w]:
            N2 -= N2_STEP
            header_msg = 'N1 speed decreased.'  
            start_stop_motor(N2_MOTOR, int(N2/N2_MAX*100))  

        N2 = np.interp(N2, [0,N2_MAX], [0,N2_MAX])


        if keys[pygame.K_3]:
            FF += FF_STEP
            header_msg = 'Fuel flow increased.'
            start_stop_motor(PUMP_MOTOR, int(FF/FF_MAX*100))
        if keys[pygame.K_e]:
            FF -= FF_STEP
            header_msg = 'Fuel flow decreased.'
            start_stop_motor(PUMP_MOTOR, int(FF/FF_MAX*100))

        FF = np.interp(FF, [0, FF_MAX], [0, FF_MAX])


        if keys[pygame.K_4]:
            OGV += OGV_STEP
            header_msg = 'OGV pitch increased.'
            rotate_motor(OGV_MOTOR, +step[OGV_MOTOR])

        if keys[pygame.K_r]:
            OGV -= OGV_STEP
            header_msg = 'OGV pitch decreased.'
            rotate_motor(OGV_MOTOR, -step[OGV_MOTOR])

        OGV = np.interp(OGV, [-OGV_MAX,OGV_MAX], [-OGV_MAX,OGV_MAX])


        if keys[pygame.K_5]:
            PCM += PCM_STEP
            header_msg = 'Fan pitch increased.'
        if keys[pygame.K_t]:
            PCM -= PCM_STEP
            header_msg = 'Fan pitch dencreased.'

        PCM = np.interp(PCM, [-PCM_MAX,PCM_MAX], [-PCM_MAX,PCM_MAX])


        if keys[pygame.K_6]:
            VBV += VBV_STEP
            header_msg = 'VBV increased.'
        if keys[pygame.K_y]:
            VBV -= VBV_STEP
            header_msg = 'VBV decreased.'

        VBV = np.interp(VBV, [-VBV_MAX, VBV_MAX], [-VBV_MAX, VBV_MAX])

        if keys[pygame.K_7]:
            VSV += VSV_STEP
            header_msg = 'VSV increased.'
        if keys[pygame.K_u]:
            VSV -= VSV_STEP
            header_msg = 'VSV decreased.'

        VSV = np.interp(VSV, [-VSV_MAX, VSV_MAX], [-VSV_MAX, VSV_MAX])

        if keys[pygame.K_8]:
            ACC += ACC_STEP
            header_msg = 'ACC increased.'
        if keys[pygame.K_i]:
            ACC -= ACC_STEP
            header_msg = 'ACC decreased.'

        ACC = np.interp(ACC, [-ACC_MAX, ACC_MAX], [-ACC_MAX, ACC_MAX])

while running:

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            
        if event.type in [pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN]:
            control(event)

        timedelta = datetime.now() - timer
        diff = timedelta.days * 24 * 3600 + timedelta.seconds
        if not locked and diff > 3:
            header_msg = ''

    draw()

    dt = clock.tick(60) / 1000

Motor1.join()
pygame.quit()
