import os, sys

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
ROOT         = os.path.dirname(BASE_DIR)
CONTENT_DIR  = os.path.join(ROOT, "content")

LAUNCH_CONF  = os.path.join(BASE_DIR, "launch.json")
RESOURCE_DIR = os.path.join(BASE_DIR, "resourcepacks")
UI_DIR       = os.path.join(BASE_DIR, "ui")
SERVERS_FILE = os.path.join(BASE_DIR, "servers.json")
NAME_FILE    = os.path.join(BASE_DIR, "name.txt")
SAVES_DIR    = os.path.join(BASE_DIR, "saves")

sys.path.insert(0, CONTENT_DIR)
from version import __VERSION__
sys.path.pop(0)


WIN_W = 1280
WIN_H = 720
FPS   = 60
WINDOW_TITLE = f"Kyklophobia  v{__VERSION__}"

# gui coords -> real/GS 640x360 logical
GS    = 2
GUI_W = WIN_W // GS
GUI_H = WIN_H // GS


BTN_SRC_W      = 200
BTN_SRC_H      = 20
BTN_Y_DISABLED = 46
BTN_Y_NORMAL   = 66
BTN_Y_HOVER    = 86

BTN_H_GUI   = 20
ENTRY_H_GUI = 40
ICON_GUI    = 36
ENTRY_PAD   = GS * 2

LIST_TOP_GUI    = 48
LIST_ITEM_PAD   = 8 * GS
LIST_BOT_GUI    = GUI_H - 64
LIST_HEIGHT_GUI = LIST_BOT_GUI - LIST_TOP_GUI

ENTRY_H  = ENTRY_H_GUI * GS
ICON_SZ  = ICON_GUI * GS
BTN_H    = BTN_H_GUI * GS
LIST_TOP = LIST_TOP_GUI * GS
LIST_BOT = LIST_BOT_GUI * GS

SS_CELL = 32

SIGNAL_W = 10
SIGNAL_H = 7
SIGNAL_Y = [16, 24, 32, 40, 48, 56]

PING_ANIM_X = 10
PING_ANIM_W = 10
PING_ANIM_H = 7
PING_ANIM_Y = [177, 185, 193, 201, 209]

BTN_BORDER = 3


WHITE  = (255, 255, 255)
GRAY   = (128, 128, 128)
DGRAY  = (80, 80, 80)
YELLOW = (255, 255, 0)
RED    = (255, 80, 80)
GREEN  = (80, 255, 80)


SPLASH_TEXTS = [
    "github.com/maladaptivesoftware",
    "Not affiliated with Mojang!",
    "Now in Python :^)",
    "Cyclopses not included!",
    "youtube.com/@maladaptivesoftware",
    "Also try Minecraft!",
    "Runs on your toaster!",
    "Milk outside a bag of milk outside\na bag of milk outside a bag of...",
    "Concrete circle.",
    "Hiya Luckies!",
    "[insert catchy caption]",
    "The cake is a lie!",
    "I AM NOT A MORON!",
    "I gently open the door.",
    "Just Monika.",
    "People die when they are killed.",
    "I am thou, thou art I.",
    "Oyashiro-sama is watching.",
    "Jabberwocky!",
    "Down the rabbit-hole!",
    "Present day. Present time.",
    "Scare Shadow!",
    "In my restless dreams,\nI see that town.",
    "Get in the robot Shinji!",
    "It's punishment time!",
    "No, that's wrong!",
    "El Psy Kongroo!",
    "GRIFFITH!",
    "Miku Miku BEEAAMMMMMM!",
    "Euphoria!",
    "Without love, it cannot be seen.",
    "I am... MAD SCIENTIST.\nSo cooool!  SONUVABITCH!",
    "Happy birthday dear Shinichi!",
    "Whats wrong, Koji?",
    "Nope youre too late i died.",
    "Tako, Ruka, maguro Fiibaa!",
    "-is the fear of circles\nor other round objects.",
    "L70070",
    "Beta Release!",
]
