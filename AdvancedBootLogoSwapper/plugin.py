# Enhanced AdvancedBootLogoSwapper Plugin with BootLogo Support
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.ConfigList import ConfigListScreen
from Components.config import config, ConfigText, ConfigSubsection, ConfigDirectory, ConfigYesNo, ConfigInteger, ConfigSelection, getConfigListEntry
from Components.Button import Button
from Components.Label import Label
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.FileList import FileList
from Components.Sources.StaticText import StaticText
from Components.Pixmap import Pixmap
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Screens.Console import Console
from enigma import eTimer, ePicLoad, getDesktop
from Components.AVSwitch import AVSwitch
import shutil
import os
import random
import subprocess
import threading
import time
from twisted.web.client import getPage
import six

# Plugin version
VER = "1.0.0"

# Plugin configuration
config.plugins.AdvancedBootLogoSwapper = ConfigSubsection()
config.plugins.AdvancedBootLogoSwapper.backdrop_enabled = ConfigYesNo(default=True)  # ON/OFF switch for backdrops
config.plugins.AdvancedBootLogoSwapper.bootlogo_enabled = ConfigYesNo(default=False)  # ON/OFF switch for bootlogos

# Backdrop settings
config.plugins.AdvancedBootLogoSwapper.backdrop_mvi_path = ConfigDirectory(default="/usr/lib/enigma2/python/Plugins/Extensions/AdvancedBootLogoSwapper/backdrops_mvi/")
config.plugins.AdvancedBootLogoSwapper.backdrop_rotation_mode = ConfigSelection(
    choices=[
        ("gui_start", "At every GUI start"),
        ("1h", "Every 1 hour"),
        ("6h", "Every 6 hours"),
        ("12h", "Every 12 hours"),
        ("24h", "Every 24 hours"),
        ("custom", "Custom interval")
    ],
    default="gui_start"
)
config.plugins.AdvancedBootLogoSwapper.backdrop_custom_interval = ConfigInteger(default=1, limits=(1, 168))
config.plugins.AdvancedBootLogoSwapper.backdrop_delete_after_convert = ConfigYesNo(default=False)
config.plugins.AdvancedBootLogoSwapper.backdrop_resolution = ConfigSelection(
    choices={"1920x1080": "1080p", "1280x720": "720p", "custom": "Custom"},
    default="1920x1080"
)
config.plugins.AdvancedBootLogoSwapper.backdrop_custom_res = ConfigText(default="1920x1080", fixed_size=False)
config.plugins.AdvancedBootLogoSwapper.backdrop_convert_quality = ConfigSelection(
    choices={"low": "Low", "medium": "Medium", "high": "High"},
    default="medium"
)

# Bootlogo settings
config.plugins.AdvancedBootLogoSwapper.bootlogo_mvi_path = ConfigDirectory(default="/usr/lib/enigma2/python/Plugins/Extensions/AdvancedBootLogoSwapper/bootlogos_mvi/")
config.plugins.AdvancedBootLogoSwapper.bootlogo_rotation_mode = ConfigSelection(
    choices=[
        ("gui_start", "At every GUI start"),
        ("1h", "Every 1 hour"),
        ("6h", "Every 6 hours"),
        ("12h", "Every 12 hours"),
        ("24h", "Every 24 hours"),
        ("custom", "Custom interval")
    ],
    default="gui_start"
)
config.plugins.AdvancedBootLogoSwapper.bootlogo_custom_interval = ConfigInteger(default=1, limits=(1, 168))
config.plugins.AdvancedBootLogoSwapper.bootlogo_delete_after_convert = ConfigYesNo(default=False)
config.plugins.AdvancedBootLogoSwapper.bootlogo_resolution = ConfigSelection(
    choices={"1920x1080": "1080p", "1280x720": "720p", "custom": "Custom"},
    default="1920x1080"
)
config.plugins.AdvancedBootLogoSwapper.bootlogo_custom_res = ConfigText(default="1920x1080", fixed_size=False)
config.plugins.AdvancedBootLogoSwapper.bootlogo_convert_quality = ConfigSelection(
    choices={"low": "Low", "medium": "Medium", "high": "High"},
    default="medium"
)

# Constants
DEFAULT_BACKUP_DIR = "/etc/enigma2/advancedbootlogoswapper/"
DEFAULT_BACKDROP = DEFAULT_BACKUP_DIR + "backdrop_default.mvi"
DEFAULT_BOOTLOGO = DEFAULT_BACKUP_DIR + "bootlogo_default.mvi"
LOG_FILE = "/tmp/AdvancedBootLogoSwapper.log"
BACKDROP_HISTORY_FILE = "/var/volatile/tmp/AdvancedBootLogoSwapper_backdrop_history.txt"
BOOTLOGO_HISTORY_FILE = "/var/volatile/tmp/AdvancedBootLogoSwapper_bootlogo_history.txt"
MAX_HISTORY = 10
SUPPORTED_SRC_FORMATS = (".jpg", ".jpeg", ".png", ".bmp")
MESSAGE_TIMEOUT = 5  # Seconds
PREVIEW_WIDTH, PREVIEW_HEIGHT = 400, 225  # Preview size
VERSION_URL = "https://raw.githubusercontent.com/popking159/abls/main/version.txt"

class AdvancedBootLogoSwapperCore:
    def __init__(self, logo_type):
        self.logo_type = logo_type  # 'backdrop' or 'bootlogo'
        self.timer = eTimer()
        self.timer.callback.append(self.swap_logo)
        self.is_active = False
        self.conversion_thread = None
        self.setup_directories()
        
    def setup_directories(self):
        # Determine paths based on logo type
        if self.logo_type == 'backdrop':
            default_file = DEFAULT_BACKDROP
            path = config.plugins.AdvancedBootLogoSwapper.backdrop_mvi_path.value
            history_file = BACKDROP_HISTORY_FILE
        else:  # bootlogo
            default_file = DEFAULT_BOOTLOGO
            path = config.plugins.AdvancedBootLogoSwapper.bootlogo_mvi_path.value
            history_file = BOOTLOGO_HISTORY_FILE
            
        # Ensure default directory exists
        default_dir = os.path.dirname(default_file)
        if not os.path.exists(default_dir):
            os.makedirs(default_dir, exist_ok=True)
            
        # Create MVI directory
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            
        # Create history directory
        history_dir = os.path.dirname(history_file)
        if not os.path.exists(history_dir):
            os.makedirs(history_dir, exist_ok=True)
    
    def start(self):
        # Only run if plugin is enabled
        if self.logo_type == 'backdrop':
            enabled = config.plugins.AdvancedBootLogoSwapper.backdrop_enabled.value
        else:
            enabled = config.plugins.AdvancedBootLogoSwapper.bootlogo_enabled.value
            
        if not enabled:
            self.restore_default_logo()
            return
            
        # Always rotate at GUI start
        self.swap_logo()
        
        # Start timer if periodic rotation is enabled
        if self.logo_type == 'backdrop':
            mode = config.plugins.AdvancedBootLogoSwapper.backdrop_rotation_mode.value
        else:
            mode = config.plugins.AdvancedBootLogoSwapper.bootlogo_rotation_mode.value
            
        if mode != "gui_start":
            self.is_active = True
            self.start_timer()
    
    def start_timer(self):
        # Determine if enabled
        if self.logo_type == 'backdrop':
            enabled = config.plugins.AdvancedBootLogoSwapper.backdrop_enabled.value
            mode = config.plugins.AdvancedBootLogoSwapper.backdrop_rotation_mode.value
            custom_interval = config.plugins.AdvancedBootLogoSwapper.backdrop_custom_interval.value
        else:
            enabled = config.plugins.AdvancedBootLogoSwapper.bootlogo_enabled.value
            mode = config.plugins.AdvancedBootLogoSwapper.bootlogo_rotation_mode.value
            custom_interval = config.plugins.AdvancedBootLogoSwapper.bootlogo_custom_interval.value
            
        if not enabled:
            return
            
        interval = 0
        
        if mode == "1h":
            interval = 3600 * 1000  # 1 hour in milliseconds
        elif mode == "6h":
            interval = 6 * 3600 * 1000
        elif mode == "12h":
            interval = 12 * 3600 * 1000
        elif mode == "24h":
            interval = 24 * 3600 * 1000
        elif mode == "custom":
            interval = custom_interval * 3600 * 1000
        
        if interval > 0:
            self.timer.start(interval, True)
    
    def stop(self):
        self.timer.stop()
        self.is_active = False
    
    def restore_default_logo(self):
        """Restore the default logo when plugin is disabled"""
        try:
            if self.logo_type == 'backdrop':
                default_file = DEFAULT_BACKDROP
                targets = ["/usr/share/backdrop.mvi", "/etc/enigma2/backdrop.mvi"]
            else:  # bootlogo
                default_file = DEFAULT_BOOTLOGO
                targets = ["/boot/bootlogo.mvi", "/usr/share/bootlogo.mvi"]
                
            if not os.path.exists(default_file):
                print(f"[AdvancedBootLogoSwapper] Default {self.logo_type} not found at {default_file}")
                return
                
            for target in targets:
                try:
                    shutil.copy(default_file, target)
                    os.chmod(target, 0o644)
                    print(f"[AdvancedBootLogoSwapper] Restored default {self.logo_type} to {target}")
                except Exception as e:
                    print(f"[AdvancedBootLogoSwapper] Restore error: {str(e)}")
        except Exception as e:
            print(f"[AdvancedBootLogoSwapper] Error restoring default: {str(e)}")
    
    def get_resolution(self):
        if self.logo_type == 'backdrop':
            res_config = config.plugins.AdvancedBootLogoSwapper.backdrop_resolution
            custom_res = config.plugins.AdvancedBootLogoSwapper.backdrop_custom_res
        else:
            res_config = config.plugins.AdvancedBootLogoSwapper.bootlogo_resolution
            custom_res = config.plugins.AdvancedBootLogoSwapper.bootlogo_custom_res
            
        if res_config.value == "custom":
            return custom_res.value
        return res_config.value
    
    def get_bitrate_for_quality(self, quality):
        return {
            "low": "15000k",
            "medium": "20000k",
            "high": "25000k"
        }[quality]
    
    def convert_to_mvi(self, source, destination, quality, delete_source=False):
        resolution = self.get_resolution()
        bitrate = self.get_bitrate_for_quality(quality)
        
        # Create temp file for m1v
        temp_m1v = destination.replace(".mvi", ".m1v")
        
        cmd = [
            "ffmpeg",
            "-i", source,
            "-r", "25",
            "-b:v", bitrate,
            "-s", resolution,
            "-c:v", "mpeg1video",
            "-f", "mpeg1video",
            "-y", temp_m1v
        ]
        
        try:
            # Create directory if needed
            os.makedirs(os.path.dirname(temp_m1v), exist_ok=True)
            
            with open(LOG_FILE, "a") as log:
                log.write(f"Starting conversion: {source} -> {destination}\n")
                log.write(f"Command: {' '.join(cmd)}\n")
                
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                
                # Stream output to log in real-time
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        log.write(output.strip() + "\n")
                
                returncode = process.poll()
                
                if returncode == 0 and os.path.exists(temp_m1v):
                    # Rename to mvi
                    os.rename(temp_m1v, destination)
                    
                    # Delete source if requested
                    if delete_source:
                        try:
                            os.remove(source)
                        except Exception as e:
                            log.write(f"Delete source failed: {str(e)}\n")
                    
                    return True
        except Exception as e:
            error_msg = f"Conversion error: {str(e)}"
            print(error_msg)
            with open(LOG_FILE, "a") as log:
                log.write(error_msg + "\n")
            # Clean up temp file if exists
            if os.path.exists(temp_m1v):
                os.remove(temp_m1v)
        
        return False
    
    def get_logos(self):
        if self.logo_type == 'backdrop':
            path = config.plugins.AdvancedBootLogoSwapper.backdrop_mvi_path.value
        else:
            path = config.plugins.AdvancedBootLogoSwapper.bootlogo_mvi_path.value
            
        return [
            os.path.join(path, f) 
            for f in os.listdir(path) 
            if os.path.isfile(os.path.join(path, f)) and 
            f.lower().endswith('.mvi')
        ]
    
    def update_history(self, path):
        if self.logo_type == 'backdrop':
            history_file = BACKDROP_HISTORY_FILE
        else:
            history_file = BOOTLOGO_HISTORY_FILE
            
        try:
            history = []
            if os.path.exists(history_file):
                with open(history_file, "r") as f:
                    history = f.read().splitlines()
            
            history = [path] + [p for p in history if p != path][:MAX_HISTORY-1]
            
            with open(history_file, "w") as f:
                f.write("\n".join(history))
        except Exception as e:
            print(f"[AdvancedBootLogoSwapper] History error: {str(e)}")
    
    def swap_logo(self):
        # Determine if enabled
        if self.logo_type == 'backdrop':
            enabled = config.plugins.AdvancedBootLogoSwapper.backdrop_enabled.value
            history_file = BACKDROP_HISTORY_FILE
        else:
            enabled = config.plugins.AdvancedBootLogoSwapper.bootlogo_enabled.value
            history_file = BOOTLOGO_HISTORY_FILE
            
        if not enabled:
            return
            
        try:
            logos = self.get_logos()
            if not logos:
                print(f"[AdvancedBootLogoSwapper] No MVI files found for {self.logo_type}! Using default.")
                self.restore_default_logo()
                return
                
            history = []
            if os.path.exists(history_file):
                with open(history_file, "r") as f:
                    history = f.read().splitlines()
            
            # Filter out recently used
            available = [b for b in logos if b not in history] or logos
            chosen = random.choice(available)
            
            self.update_history(chosen)
            
            if self.logo_type == 'backdrop':
                targets = ["/usr/share/backdrop.mvi", "/etc/enigma2/backdrop.mvi"]
            else:  # bootlogo
                targets = ["/boot/bootlogo.mvi", "/usr/share/bootlogo.mvi"]
            
            for target in targets:
                try:
                    shutil.copy(chosen, target)
                    os.chmod(target, 0o644)
                    print(f"[AdvancedBootLogoSwapper] Set {self.logo_type}: {os.path.basename(chosen)}")
                except Exception as e:
                    print(f"[AdvancedBootLogoSwapper] Copy error: {str(e)}")
        finally:
            # Restart timer if periodic rotation is enabled
            if self.is_active:
                self.start_timer()
    
    def convert_directory_images(self, directory, quality, delete_source, callback):
        converted = 0
        errors = []
        
        # Ensure directory exists
        if not os.path.exists(directory):
            errors.append(f"Directory not found: {directory}")
            callback(converted, errors)
            return
            
        for file in os.listdir(directory):
            src_file = os.path.join(directory, file)
            if not os.path.isfile(src_file):
                continue
                
            ext = os.path.splitext(file)[1].lower()
            if ext not in SUPPORTED_SRC_FORMATS:
                continue
            
            base_name = os.path.splitext(file)[0]
            if self.logo_type == 'backdrop':
                dest_dir = config.plugins.AdvancedBootLogoSwapper.backdrop_mvi_path.value
            else:
                dest_dir = config.plugins.AdvancedBootLogoSwapper.bootlogo_mvi_path.value
                
            dest_file = os.path.join(dest_dir, f"{base_name}.mvi")
            
            if self.convert_to_mvi(src_file, dest_file, quality, delete_source):
                converted += 1
            else:
                errors.append(f"Conversion failed: {file}")
        
        # Return results to callback
        callback(converted, errors)

def initialize_default_backup():
    """Create backup directory and save original logos if they don't exist"""
    try:
        # Create directory if needed
        if not os.path.exists(DEFAULT_BACKUP_DIR):
            os.makedirs(DEFAULT_BACKUP_DIR, exist_ok=True)
            print(f"[AdvancedBootLogoSwapper] Created backup directory: {DEFAULT_BACKUP_DIR}")

        # Backup bootlogo if doesn't exist
        if not os.path.exists(DEFAULT_BOOTLOGO):
            for source in ["/boot/bootlogo.mvi", "/usr/share/bootlogo.mvi"]:
                if os.path.exists(source):
                    try:
                        # Handle symlinks
                        if os.path.islink(source):
                            real_source = os.readlink(source)
                            if not os.path.isabs(real_source):
                                real_source = os.path.join(os.path.dirname(source), real_source)
                            shutil.copy(real_source, DEFAULT_BOOTLOGO)
                        else:
                            shutil.copy(source, DEFAULT_BOOTLOGO)
                        os.chmod(DEFAULT_BOOTLOGO, 0o644)
                        print(f"[AdvancedBootLogoSwapper] Backed up bootlogo from {source} to {DEFAULT_BOOTLOGO}")
                        break
                    except Exception as e:
                        print(f"[AdvancedBootLogoSwapper] Bootlogo backup error: {str(e)}")

        # Backup backdrop if doesn't exist
        if not os.path.exists(DEFAULT_BACKDROP):
            for source in ["/usr/share/backdrop.mvi"]:
                if os.path.exists(source):
                    try:
                        # Handle symlinks
                        if os.path.islink(source):
                            real_source = os.readlink(source)
                            if not os.path.isabs(real_source):
                                real_source = os.path.join(os.path.dirname(source), real_source)
                            shutil.copy(real_source, DEFAULT_BACKDROP)
                        else:
                            shutil.copy(source, DEFAULT_BACKDROP)
                        os.chmod(DEFAULT_BACKDROP, 0o644)
                        print(f"[AdvancedBootLogoSwapper] Backed up backdrop from {source} to {DEFAULT_BACKDROP}")
                        break
                    except Exception as e:
                        print(f"[AdvancedBootLogoSwapper] Backdrop backup error: {str(e)}")
    except Exception as e:
        print(f"[AdvancedBootLogoSwapper] Error initializing default backup: {str(e)}")

# Plugin main instances
backdrop_core = AdvancedBootLogoSwapperCore('backdrop')
bootlogo_core = AdvancedBootLogoSwapperCore('bootlogo')

def autostart(reason, **kwargs):
    if reason == 0:  # System startup
        # Initialize default backups first
        initialize_default_backup()
        
        if config.plugins.AdvancedBootLogoSwapper.backdrop_enabled.value:
            backdrop_core.start()
        else:
            backdrop_core.restore_default_logo()
            
        if config.plugins.AdvancedBootLogoSwapper.bootlogo_enabled.value:
            bootlogo_core.start()
        else:
            bootlogo_core.restore_default_logo()
            
    elif reason == 1:  # System shutdown
        backdrop_core.stop()
        bootlogo_core.stop()

# START SCREEN
class StartScreen(Screen):
    skin = """
        <screen position="center,center" size="1000,700" title="Advanced BootLogo Swapper" flags="wfNoBorder">
            <eLabel name="background" position="0,0" size="1000,700" zPosition="-99" backgroundColor="background" />
            <widget name="title" position="10,10" size="980,50" font="Regular; 22" halign="left" valign="center" transparent="1" foregroundColor="white" />
            
            <!-- Backdrops Button -->
            <eLabel name="backdrop_button" position="100,100" size="350,250" zPosition="1" backgroundColor="green" />
            <widget name="backdrop_label" position="100,360" size="350,50" font="Regular; 22" halign="center" valign="center" transparent="1" foregroundColor="white" />
            
            <!-- Bootlogos Button -->
            <eLabel name="bootlogo_button" position="550,100" size="350,250" zPosition="1" backgroundColor="yellow" />
            <widget name="bootlogo_label" position="550,360" size="350,50" font="Regular; 22" halign="center" valign="center" transparent="1" foregroundColor="white" />
            
            <!-- Status Bar -->
            <widget name="status" position="10,586" size="980,50" font="Regular; 22" halign="left" valign="center" transparent="1" foregroundColor="white" />
            
            <!-- Bottom Buttons -->
            <widget source="key_red" render="Label" position="10,650" size="180,40" backgroundColor="key_red" font="Regular;20" valign="center" halign="center" />
            <widget source="key_green" render="Label" position="200,650" size="180,40" backgroundColor="key_green" font="Regular;20" valign="center" halign="center" />
            <widget source="key_yellow" render="Label" position="390,650" size="180,40" backgroundColor="key_yellow" font="Regular;20" valign="center" halign="center" />
            <widget source="key_blue" render="Label" position="580,650" size="180,40" backgroundColor="key_blue" font="Regular;20" valign="center" halign="center" />
            
            <eLabel position="10,640" size="980,2" backgroundColor="darkgrey" />
        </screen>
    """
    
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.setTitle("Advanced BootLogo Swapper")
        
        # Title
        self["title"] = Label(f"Advanced BootLogo Swapper v{VER}")
        
        # Status label
        self["status"] = Label("Checking for updates...")
        
        # Button labels
        self["key_red"] = StaticText(_("Exit"))
        self["key_green"] = StaticText(_("Backdrops"))
        self["key_yellow"] = StaticText(_("Bootlogos"))
        self["key_blue"] = StaticText(_("About"))
        
        # Feature labels
        self["backdrop_label"] = Label(_("Backdrops"))
        self["bootlogo_label"] = Label(_("Boot Logos"))
        
        self["actions"] = ActionMap(["SetupActions", "ColorActions"], {
            "red": self.close,
            "green": self.openBackdrops,
            "yellow": self.openBootlogos,
            "blue": self.showAbout,
            "cancel": self.close,
        }, -2)
        
        self.onFirstExecBegin.append(self.checkUpdates)
    
    def checkUpdates(self):
        """Check for plugin updates online"""
        try:
            getPage(six.ensure_binary(VERSION_URL), timeout=10).addCallback(self.parseUpdateData).addErrback(self.updateError)
        except Exception as e:
            self["status"].setText(f"Update check error: {str(e)}")
            print(f"[AdvancedBootLogoSwapper] Update check error: {str(e)}")
    
    def updateError(self, error):
        """Handle update check errors"""
        error_msg = f"Update failed: {str(error)}"
        self["status"].setText(error_msg)
        print(f"[AdvancedBootLogoSwapper] {error_msg}")
    
    def parseUpdateData(self, data):
        """Parse version data from GitHub"""
        if six.PY3:
            data = data.decode("utf-8")
        else:
            data = data.encode("utf-8")
        
        new_version = None
        description = None
        
        if data:
            lines = data.split("\n")
            for line in lines:
                if line.startswith("version="):
                    # Extract version value
                    version_str = line.split("=")[1].strip()
                    if version_str.startswith("'") or version_str.startswith('"'):
                        new_version = version_str[1:-1]
                    else:
                        new_version = version_str
                elif line.startswith("description="):
                    # Extract description value
                    desc_str = line.split("=")[1].strip()
                    if desc_str.startswith("'") or desc_str.startswith('"'):
                        description = desc_str[1:-1]
                    else:
                        description = desc_str
        
        if new_version and new_version != VER:
            self["status"].setText(f"Update available: v{new_version}")
            message = f"New version v{new_version} is available!\n\n{description}\n\nDo you want to update now?"
            self.session.openWithCallback(
                lambda answer: self.installUpdate(answer), 
                MessageBox, 
                message, 
                MessageBox.TYPE_YESNO,
                timeout=10
            )
        else:
            self["status"].setText(f"Plugin is up to date (v{VER})")
    
    def installUpdate(self, answer):
        """Install plugin update using one-line installer"""
        if not answer:
            return
        
        self["status"].setText("Starting update installation...")
        cmd = "wget -q --no-check-certificate https://raw.githubusercontent.com/popking159/abls/main/installer.sh -O - | /bin/sh"
        self.session.open(
            Console,
            title=_("Updating Advanced BootLogo Swapper..."),
            cmdlist=[cmd],
            closeOnSuccess=False
        )
    
    def openBackdrops(self):
        self.session.open(BackdropConfigScreen)
    
    def openBootlogos(self):
        self.session.open(BootlogoConfigScreen)
    
    def showAbout(self):
        self.session.open(MessageBox, 
            f"Advanced BootLogo Swapper v{VER}\n\n"
            "#>> Author: MNASR <<#\n"
            " --------------------- \n"
            "• Manage backdrops (GUI backgrounds)\n"
            "• Manage bootlogos (startup screens)\n"
            "• Automatic rotation of images\n"
            "• Custom conversion settings",
            MessageBox.TYPE_INFO
        )

class FolderSelect(Screen):
    skin = """
        <screen position="center,center" size="1000,700" title="Select Folder" flags="wfNoBorder">
            <eLabel name="" position="0, 0" size="1000,700" zPosition="-99" />
            <widget name="title" position="10,10" size="980,50" font="Regular; 22" halign="left" valign="center" transparent="1" foregroundColor="white" />
            <widget name="filelist" position="10,75" size="980,495" scrollbarMode="showOnDemand" itemHeight="45" font="Regular; 26" />
            <widget name="folderinfo" position="10,586" size="980,50" font="Regular; 22" halign="left" valign="center" transparent="1" foregroundColor="white" />
            <widget source="key_red" render="Label" position="10,650" size="180,40" backgroundColor="key_red" font="Regular;20" valign="center" halign="center" />
            <widget source="key_green" render="Label" position="200,650" size="180,40" backgroundColor="key_green" font="Regular;20" valign="center" halign="center" />
            <eLabel position="10,640" size="980,2" backgroundColor="darkgrey" />
        </screen>
    """
    
    def __init__(self, session, current_dir):
        Screen.__init__(self, session)
        self.session = session
        
        # Set title widget
        self["title"] = Label("Select Folder")
        self["folderinfo"] = Label()
        
        self["key_red"] = StaticText(_("Cancel"))
        self["key_green"] = StaticText(_("Select"))
        
        # Start with root directory if none provided
        if not current_dir or not os.path.exists(current_dir):
            current_dir = "/"
        
        self["filelist"] = FileList(
            current_dir,
            showDirectories=True,
            showFiles=False,
            showMountpoints=True,
            useServiceRef=False
        )
        
        self["actions"] = ActionMap(["SetupActions", "ColorActions"],
        {
            "cancel": self.cancel,
            "red": self.cancel,
            "green": self.select,
            "ok": self.ok,
        }, -2)
        
        # Update folder info immediately
        self.updateFolderInfo()
    
    def updateFolderInfo(self):
        current_dir = self["filelist"].getCurrentDirectory()
        self["folderinfo"].setText(f"Current Folder: {current_dir}")
    
    def ok(self):
        current = self["filelist"].getCurrent()
        if current and self["filelist"].canDescent():
            self["filelist"].descent()
            self.updateFolderInfo()
    
    def select(self):
        current_dir = self["filelist"].getCurrentDirectory()
        # Ensure directory path ends with /
        if not current_dir.endswith('/'):
            current_dir += '/'
        self.close(current_dir)
    
    def cancel(self):
        self.close(None)

class CustomChoiceBox(ChoiceBox):
    skin = """
        <screen position="center,center" size="1000,700" title="Choice Box" flags="wfNoBorder">
<eLabel name="" position="0, 0" size="1000,700" zPosition="-99" />
<eLabel position="10,640" size="980,2" backgroundColor="darkgrey" />
<widget source="title" render="Label" position="10,10" size="980,50" font="Regular; 22" halign="left" valign="center" transparent="1" foregroundColor="white" />
<widget name="list" position="10,75" size="980,496" scrollbarMode="showNever" itemHeight="62" font="Regular; 26" />
<eLabel name="" position="10,650" size="180,40" backgroundColor="black" font="Regular;20" valign="center" halign="center" text="Exit" />
</screen>
    """
    
    def __init__(self, session, title="", list=None, keys=None, selection=0, skin_name=None):
        # Use our custom skin
        ChoiceBox.__init__(self, session, title, list, keys, selection, skin_name="")
        self.skinName = "CustomChoiceBox"
        self["title"] = Label("Image Options")
    
    def exit(self):
        self.close()

class BaseConfigScreen(ConfigListScreen, Screen):
    skin = """
        <screen position="center,center" size="1000,700" title="Advanced BootLogo Swapper Settings" flags="wfNoBorder">
            <widget name="config" position="10,75" size="980,495" scrollbarMode="showOnDemand" itemHeight="45" font="Regular; 26" />
            <widget source="key_red" render="Label" position="10,650" size="180,40" backgroundColor="key_red" font="Regular;20" valign="center" halign="center" />
            <widget source="key_green" render="Label" position="200,650" size="180,40" backgroundColor="key_green" font="Regular;20" valign="center" halign="center" />
            <widget source="key_yellow" render="Label" position="390,650" size="180,40" backgroundColor="key_yellow" font="Regular;20" valign="center" halign="center" />
            <eLabel position="10,640" size="980,2" backgroundColor="darkgrey" />
            <widget name="status" position="10,586" size="980,50" font="Regular; 22" halign="left" valign="center" transparent="1" foregroundColor="white" />
            <eLabel name="" position="0, 0" size="1000,700" zPosition="-99" />
            <widget name="title" position="10,10" size="980,50" font="Regular; 22" halign="left" valign="center" transparent="1" foregroundColor="white" />
        </screen>
    """
    
        
    def __init__(self, session, logo_type):
        self.logo_type = logo_type
        Screen.__init__(self, session)
        self.session = session
        self.initial_enabled_state = self.get_config('enabled').value
        
        # Create config list
        ConfigListScreen.__init__(self, [], session=session)
        self["status"] = Label("")
        self["title"] = Label(f"{logo_type.capitalize()} Settings - Advanced BootLogo Swapper v{VER}")
        
        # Setup buttons
        self["key_red"] = Button(_("Cancel"))
        self["key_green"] = Button(_("Save"))
        self["key_yellow"] = Button(_("Browse Images"))
        
        self["actions"] = ActionMap(["SetupActions", "ColorActions", "InfoActions"], {
            "cancel": self.keyCancel,
            "save": self.keySave,
            "yellow": self.browseImages,
            "ok": self.keyOK,
            'info': self.info,
        }, -2)
        
        self.onChangedEntry = []
        self.list = []
        self.initConfigList()
    
    def get_config(self, name):
        """Get config item based on logo type"""
        prefix = 'backdrop' if self.logo_type == 'backdrop' else 'bootlogo'
        return getattr(config.plugins.AdvancedBootLogoSwapper, f"{prefix}_{name}")
    
    def initConfigList(self):
        self.list = [
            getConfigListEntry(f"Enable {self.logo_type.capitalize()} Rotation", self.get_config('enabled'))
        ]
        
        # Only show other settings if plugin is enabled
        if self.get_config('enabled').value:
            self.list += [
                getConfigListEntry("MVI Directory", self.get_config('mvi_path')),
                getConfigListEntry("Rotation Mode", self.get_config('rotation_mode')),
            ]
            
            # Only show custom interval if custom mode is selected
            if self.get_config('rotation_mode').value == "custom":
                self.list.append(
                    getConfigListEntry("Custom Interval (hours)", self.get_config('custom_interval'))
                )
                
            self.list += [
                getConfigListEntry("Delete After Convert", self.get_config('delete_after_convert')),
                getConfigListEntry("Resolution", self.get_config('resolution')),
            ]
            
            # Only show custom resolution if custom is selected
            if self.get_config('resolution').value == "custom":
                self.list.append(
                    getConfigListEntry("Custom Resolution", self.get_config('custom_res'))
                )
                
            self.list.append(
                getConfigListEntry("Default Conversion Quality", self.get_config('convert_quality'))
            )
        
        self["config"].list = self.list
        self["config"].l.setList(self.list)
    
    def changed(self):
        current = self["config"].getCurrent()
        if current:
            # If enabled state changed, rebuild the list
            if current[1] == self.get_config('enabled'):
                self.initConfigList()
            # Update list when rotation mode changes
            elif current[1] == self.get_config('rotation_mode'):
                self.initConfigList()
            # Update list when resolution changes
            elif current[1] == self.get_config('resolution'):
                self.initConfigList()
    
    def openFolderBrowser(self, config_item):
        """Open folder browser for the specified config item"""
        current_path = config_item.value
        self.session.openWithCallback(
            lambda path: self.folderSelected(path, config_item),
            FolderSelect,
            current_path
        )
    
    def folderSelected(self, path, config_item):
        """Callback when a folder is selected"""
        if path:
            config_item.value = path
            self["config"].invalidateCurrent()
    
    def keyLeft(self):
        current = self["config"].getCurrent()
        if current:
            if current[1] in [self.get_config('mvi_path')]:
                self.openFolderBrowser(current[1])
            else:
                ConfigListScreen.keyLeft(self)
    
    def keyRight(self):
        current = self["config"].getCurrent()
        if current:
            if current[1] in [self.get_config('mvi_path')]:
                self.openFolderBrowser(current[1])
            else:
                ConfigListScreen.keyRight(self)
    
    # Add keyOK method to handle OK button press
    def keyOK(self):
        current = self["config"].getCurrent()
        if current:
            if current[1] in [self.get_config('mvi_path')]:
                self.openFolderBrowser(current[1])
            else:
                ConfigListScreen.keyOK(self)
    
    def browseImages(self):
        # Only allow browsing if plugin is enabled
        if self.get_config('enabled').value:
            self.session.open(ImageBrowser, self.logo_type)
        else:
            self.session.open(
                MessageBox, 
                f"Please enable {self.logo_type} rotation first!", 
                MessageBox.TYPE_INFO,
                timeout=MESSAGE_TIMEOUT
            )
    
    def keySave(self):
        self.saveAll()
        self["status"].setText("Saving settings...")
        
        # Handle plugin state change
        if self.logo_type == 'backdrop':
            core = backdrop_core
        else:
            core = bootlogo_core
            
        # Stop the core
        core.stop()
        
        if self.get_config('enabled').value:
            # If enabling, start the core
            core.start()
            message = f"{self.logo_type.capitalize()} settings saved and activated!"
        else:
            # If disabling, restore default logo
            core.restore_default_logo()
            message = f"{self.logo_type.capitalize()} settings saved and deactivated!"
        
        self.session.open(
            MessageBox, 
            message, 
            MessageBox.TYPE_INFO,
            timeout=MESSAGE_TIMEOUT
        )
        self.close(True)

    def info(self):
        aboutbox = self.session.open(MessageBox, _('Advanced BootLogo Swapper v.%s') % VER, MessageBox.TYPE_INFO)
        aboutbox.setTitle(_('Info...'))

class BackdropConfigScreen(BaseConfigScreen):
    def __init__(self, session):
        super().__init__(session, 'backdrop')

class BootlogoConfigScreen(BaseConfigScreen):
    def __init__(self, session):
        super().__init__(session, 'bootlogo')

class ImageBrowser(Screen):
    skin = """
        <screen position="center,center" size="1000,700" title="Image Browser" flags="wfNoBorder">
            <eLabel name="" position="0, 0" size="1000,700" zPosition="-99" />
            <widget name="title" position="10,10" size="980,50" font="Regular; 22" halign="left" valign="center" transparent="1" foregroundColor="white" />
            <widget name="filelist" position="10,75" size="980,495" scrollbarMode="showOnDemand" itemHeight="45" font="Regular; 26" />
            <widget name="fileinfo" position="10,586" size="980,50" font="Regular; 22" halign="left" valign="center" transparent="1" foregroundColor="white" />
            <widget source="key_red" render="Label" position="10,650" size="180,40" backgroundColor="key_red" font="Regular;20" valign="center" halign="center" />
            <widget source="key_green" render="Label" position="200,650" size="180,40" backgroundColor="key_green" font="Regular;20" valign="center" halign="center" />
            <widget source="key_yellow" render="Label" position="390,650" size="180,40" backgroundColor="key_yellow" font="Regular;20" valign="center" halign="center" />
            <eLabel position="10,640" size="980,2" backgroundColor="darkgrey" />
        </screen>
    """

    def __init__(self, session, logo_type):
        Screen.__init__(self, session)
        self.session = session
        self.logo_type = logo_type
        self.setTitle(f"{logo_type.capitalize()} Image Browser")
        
        # Start from root directory
        self.start_path = "/"
        
        # Setup file list - allow browsing anywhere
        self.filelist = FileList(
            self.start_path,
            showDirectories=True,
            showFiles=True,
            showMountpoints=True,
            useServiceRef=False,
            matchingPattern=".*\.(jpg|jpeg|png|bmp)$"
        )
        self["filelist"] = self.filelist
        
        # Setup info label
        self["fileinfo"] = Label()
        
        # Setup title widget
        self["title"] = Label(f"{logo_type.capitalize()} Image Browser - Advanced BootLogo Swapper v{VER}")
        
        # Setup buttons
        self["key_red"] = StaticText(_("Back"))
        self["key_green"] = StaticText(_("Convert"))
        self["key_yellow"] = StaticText(_("Menu"))
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "MenuActions"], {
            "cancel": self.exit,
            "red": self.exit,
            "green": self.convertCurrent,
            "yellow": self.openMenu,
            "ok": self.okClicked,
            "left": self.left,
            "right": self.right,
            "down": self.down,
            "up": self.up,
            "menu": self.openMenu
        }, -1)
        
        self.onLayoutFinish.append(self.layoutFinished)

    def layoutFinished(self):
        self.updateFileInfo()

    def up(self):
        self["filelist"].up()
        self.updateFileInfo()

    def down(self):
        self["filelist"].down()
        self.updateFileInfo()

    def left(self):
        self["filelist"].pageUp()
        self.updateFileInfo()

    def right(self):
        self["filelist"].pageDown()
        self.updateFileInfo()

    def updateFileInfo(self):
        try:
            current = self["filelist"].getCurrent()
            if not current:
                self["fileinfo"].setText("")
                return
                
            filename = current[0][0]
            current_dir = self["filelist"].getCurrentDirectory()
            
            # Ensure we have valid directory
            if current_dir is None:
                current_dir = "/"
            
            path = os.path.join(current_dir, filename)
            
            # Update file info
            if os.path.isfile(path):
                size = os.path.getsize(path) // 1024  # Size in KB
                self["fileinfo"].setText(f"{filename} - {size} KB")
            else:
                self["fileinfo"].setText(filename)
        except Exception as e:
            print(f"[ImageBrowser] Error in updateFileInfo: {str(e)}")
            self["fileinfo"].setText("Error loading file info")

    def okClicked(self):
        if self.filelist.canDescent():
            self.filelist.descent()
            self.updateFileInfo()

    def openMenu(self):
        current = self["filelist"].getCurrent()
        if not current:
            return
            
        # Get full path
        current_dir = self["filelist"].getCurrentDirectory()
        filename = current[0][0]
        path = os.path.join(current_dir, filename) if filename else current_dir
        
        options = []
        
        if os.path.isfile(path):
            # Single file options
            options.append((f"Convert this image (High Quality)", ("single", "high")))
            options.append((f"Convert this image (Medium Quality)", ("single", "medium")))
            options.append((f"Convert this image (Low Quality)", ("single", "low")))
            
            # Add delete option
            options.append((f"Delete this image", "delete"))
        
        # Always show directory options
        options.append((f"Convert all images in this directory", "all"))
        
        self.session.openWithCallback(
            self.menuCallback,
            CustomChoiceBox,
            title="Image Options",
            list=options
        )

    def menuCallback(self, choice):
        if not choice:
            return
            
        action = choice[1]
        
        if isinstance(action, tuple) and action[0] == "single":
            quality = action[1]
            self.convertImage(quality)
        elif action == "all":
            self.convertAllInDirectory()
        elif action == "delete":
            self.deleteCurrentImage()

    def convertCurrent(self):
        # Get default quality based on logo type
        if self.logo_type == 'backdrop':
            quality = config.plugins.AdvancedBootLogoSwapper.backdrop_convert_quality.value
        else:
            quality = config.plugins.AdvancedBootLogoSwapper.bootlogo_convert_quality.value
            
        self.convertImage(quality)

    def convertImage(self, quality):
        current = self["filelist"].getCurrent()
        if not current:
            return
            
        # Get current selection
        selected = self["filelist"].getFilename()
        if not selected:
            return
            
        # Get full path
        current_dir = self["filelist"].getCurrentDirectory()
        if not current_dir:
            current_dir = "/"
            
        src_file = os.path.join(current_dir, selected)
        if not os.path.isfile(src_file):
            return
            
        base_name = os.path.splitext(os.path.basename(src_file))[0]
        if self.logo_type == 'backdrop':
            dest_dir = config.plugins.AdvancedBootLogoSwapper.backdrop_mvi_path.value
            delete_after = config.plugins.AdvancedBootLogoSwapper.backdrop_delete_after_convert.value
            core = backdrop_core
        else:
            dest_dir = config.plugins.AdvancedBootLogoSwapper.bootlogo_mvi_path.value
            delete_after = config.plugins.AdvancedBootLogoSwapper.bootlogo_delete_after_convert.value
            core = bootlogo_core
            
        dest_file = os.path.join(dest_dir, f"{base_name}.mvi")
        
        # Create destination directory if needed
        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
        
        # Start conversion
        def conversion_task():
            try:
                # Determine which core to use based on logo type
                if self.logo_type == 'backdrop':
                    core = backdrop_core
                    delete_after = config.plugins.AdvancedBootLogoSwapper.backdrop_delete_after_convert.value
                else:
                    core = bootlogo_core
                    delete_after = config.plugins.AdvancedBootLogoSwapper.bootlogo_delete_after_convert.value
                
                success = core.convert_to_mvi(
                    src_file, 
                    dest_file, 
                    quality, 
                    delete_after
                )
                
                if success:
                    self.session.open(
                        MessageBox, 
                        f"Successfully converted to {quality} quality!", 
                        MessageBox.TYPE_INFO,
                        timeout=MESSAGE_TIMEOUT
                    )
                else:
                    self.session.open(
                        MessageBox, 
                        "Conversion failed! Check log for details.", 
                        MessageBox.TYPE_ERROR,
                        timeout=MESSAGE_TIMEOUT
                    )
            except Exception as e:
                self.session.open(
                    MessageBox, 
                    f"Error during conversion: {str(e)}", 
                    MessageBox.TYPE_ERROR,
                    timeout=MESSAGE_TIMEOUT
                )
        
        threading.Thread(target=conversion_task).start()
        self.session.open(
            MessageBox, 
            "Conversion started in background...", 
            MessageBox.TYPE_INFO,
            timeout=MESSAGE_TIMEOUT
        )

    def convertAllInDirectory(self):
        current_dir = self["filelist"].getCurrentDirectory()
        if not current_dir:
            return
            
        # Get settings based on logo type
        if self.logo_type == 'backdrop':
            quality = config.plugins.AdvancedBootLogoSwapper.backdrop_convert_quality.value
            delete_source = config.plugins.AdvancedBootLogoSwapper.backdrop_delete_after_convert.value
            core = backdrop_core
        else:
            quality = config.plugins.AdvancedBootLogoSwapper.bootlogo_convert_quality.value
            delete_source = config.plugins.AdvancedBootLogoSwapper.bootlogo_delete_after_convert.value
            core = bootlogo_core
        
        # Check if directory exists
        if not os.path.exists(current_dir):
            self.session.open(
                MessageBox, 
                f"Directory not found: {current_dir}", 
                MessageBox.TYPE_ERROR,
                timeout=MESSAGE_TIMEOUT
            )
            return
            
        # Count images to convert
        image_files = []
        for file in os.listdir(current_dir):
            src_file = os.path.join(current_dir, file)
            if not os.path.isfile(src_file):
                continue
                
            ext = os.path.splitext(file)[1].lower()
            if ext in SUPPORTED_SRC_FORMATS:
                image_files.append(file)
        
        if not image_files:
            self.session.open(
                MessageBox, 
                "No supported images found in this directory!",
                MessageBox.TYPE_WARNING,
                timeout=MESSAGE_TIMEOUT
            )
            return
            
        # Start conversion in background thread
        def conversion_task():
            converted = 0
            errors = []
            
            for file in image_files:
                src_file = os.path.join(current_dir, file)
                if not os.path.isfile(src_file):
                    continue
                    
                base_name = os.path.splitext(file)[0]
                dest_file = os.path.join(config.plugins.AdvancedBootLogoSwapper.mvi_path.value, f"{base_name}.mvi")
                
                if swapper_core.convert_to_mvi(src_file, dest_file, quality, delete_source):
                    converted += 1
                else:
                    errors.append(f"Conversion failed: {file}")
            
            # Show results
            message = f"Converted {converted}/{len(image_files)} images!"
            if errors:
                message += f"\n\nErrors occurred with:\n" + "\n".join(errors[:3])
                if len(errors) > 3:
                    message += f"\n...and {len(errors)-3} more"
            
            self.session.open(
                MessageBox, 
                message, 
                MessageBox.TYPE_INFO,
                timeout=MESSAGE_TIMEOUT
            )
        
        threading.Thread(target=conversion_task).start()
        self.session.open(
            MessageBox, 
            f"Converting {len(image_files)} images in background...", 
            MessageBox.TYPE_INFO,
            timeout=MESSAGE_TIMEOUT
        )

    def deleteCurrentImage(self):
        current = self["filelist"].getCurrent()
        if not current:
            return
            
        # Get current selection
        selected = self["filelist"].getFilename()
        if not selected:
            return
            
        # Get full path
        current_dir = self["filelist"].getCurrentDirectory()
        if not current_dir:
            current_dir = "/"
            
        path = os.path.join(current_dir, selected)
        if not os.path.isfile(path):
            return
            
        # Confirm deletion
        self.session.openWithCallback(
            lambda result: self.confirmDelete(result, path),
            MessageBox,
            f"Delete this image?\n{selected}",
            MessageBox.TYPE_YESNO
        )

    def confirmDelete(self, result, path):
        if result:
            try:
                os.remove(path)
                self.session.open(
                    MessageBox, 
                    "Image deleted successfully!", 
                    MessageBox.TYPE_INFO,
                    timeout=MESSAGE_TIMEOUT
                )
                # Refresh file list
                self.filelist.refresh()
            except Exception as e:
                self.session.open(
                    MessageBox, 
                    f"Delete failed: {str(e)}", 
                    MessageBox.TYPE_ERROR,
                    timeout=MESSAGE_TIMEOUT
                )

    def exit(self):
        self.close()

# Plugin descriptor
def openStartScreen(session, **kwargs):
    session.open(StartScreen)

def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name="Advanced BootLogo Swapper",
            description="Automatic Boot Logo and Backdrop Rotation",
            where=PluginDescriptor.WHERE_AUTOSTART,
            fnc=autostart
        ),
        PluginDescriptor(
            name="Advanced BootLogo Swapper",
            description=f"Configure backdrop and bootlogo rotation (v{VER}) By MNASR",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon="plugin.png",
            fnc=openStartScreen
        )
    ]