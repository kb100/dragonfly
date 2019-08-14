#
# This file is part of Dragonfly.
# (c) Copyright 2007, 2008 by Christo Butcher
# Licensed under the LGPL.
#
#   Dragonfly is free software: you can redistribute it and/or modify it
#   under the terms of the GNU Lesser General Public License as published
#   by the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   Dragonfly is distributed in the hope that it will be useful, but
#   WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public
#   License along with Dragonfly.  If not, see
#   <http://www.gnu.org/licenses/>.
#

"""This file implements the Win32 keyboard interface using sendinput."""

from contextlib import contextmanager
from ctypes import windll
from locale import getpreferredencoding
import time

from six import binary_type, string_types

import win32api
import win32con
import win32gui
import win32process

from ._base import BaseKeyboard, Typeable as BaseTypeable
from ..sendinput import KeyboardInput, make_input_array, send_input_array


class Win32KeySymbols(object):
    """ Key symbols for win32. """

    # Whitespace and editing keys
    RETURN = win32con.VK_RETURN
    TAB = win32con.VK_TAB
    SPACE = win32con.VK_SPACE
    BACK = win32con.VK_BACK
    DELETE = win32con.VK_DELETE

    # Main modifier keys
    SHIFT = win32con.VK_SHIFT
    CONTROL = win32con.VK_CONTROL
    ALT = win32con.VK_MENU

    # Right modifier keys
    RSHIFT = win32con.VK_RSHIFT
    RCONTROL = win32con.VK_RCONTROL
    RALT = win32con.VK_RMENU

    # Special keys
    ESCAPE = win32con.VK_ESCAPE
    INSERT = win32con.VK_INSERT
    PAUSE = win32con.VK_PAUSE
    LSUPER = win32con.VK_LWIN
    RSUPER = win32con.VK_RWIN
    APPS = win32con.VK_APPS
    SNAPSHOT = win32con.VK_SNAPSHOT

    # Lock keys
    SCROLL_LOCK = win32con.VK_SCROLL
    NUM_LOCK = win32con.VK_NUMLOCK
    CAPS_LOCK = win32con.VK_CAPITAL

    # Navigation keys
    UP = win32con.VK_UP
    DOWN = win32con.VK_DOWN
    LEFT = win32con.VK_LEFT
    RIGHT = win32con.VK_RIGHT
    PAGE_UP = win32con.VK_PRIOR
    PAGE_DOWN = win32con.VK_NEXT
    HOME = win32con.VK_HOME
    END = win32con.VK_END

    # Number pad keys
    MULTIPLY = win32con.VK_MULTIPLY
    ADD = win32con.VK_ADD
    SEPARATOR = win32con.VK_SEPARATOR
    SUBTRACT = win32con.VK_SUBTRACT
    DECIMAL = win32con.VK_DECIMAL
    DIVIDE = win32con.VK_DIVIDE
    NUMPAD0 = win32con.VK_NUMPAD0
    NUMPAD1 = win32con.VK_NUMPAD1
    NUMPAD2 = win32con.VK_NUMPAD2
    NUMPAD3 = win32con.VK_NUMPAD3
    NUMPAD4 = win32con.VK_NUMPAD4
    NUMPAD5 = win32con.VK_NUMPAD5
    NUMPAD6 = win32con.VK_NUMPAD6
    NUMPAD7 = win32con.VK_NUMPAD7
    NUMPAD8 = win32con.VK_NUMPAD8
    NUMPAD9 = win32con.VK_NUMPAD9

    # Function keys
    F1 = win32con.VK_F1
    F2 = win32con.VK_F2
    F3 = win32con.VK_F3
    F4 = win32con.VK_F4
    F5 = win32con.VK_F5
    F6 = win32con.VK_F6
    F7 = win32con.VK_F7
    F8 = win32con.VK_F8
    F9 = win32con.VK_F9
    F10 = win32con.VK_F10
    F11 = win32con.VK_F11
    F12 = win32con.VK_F12
    F13 = win32con.VK_F13
    F14 = win32con.VK_F14
    F15 = win32con.VK_F15
    F16 = win32con.VK_F16
    F17 = win32con.VK_F17
    F18 = win32con.VK_F18
    F19 = win32con.VK_F19
    F20 = win32con.VK_F20
    F21 = win32con.VK_F21
    F22 = win32con.VK_F22
    F23 = win32con.VK_F23
    F24 = win32con.VK_F24

    # Multimedia keys
    VOLUME_UP = win32con.VK_VOLUME_UP
    VOLUME_DOWN = win32con.VK_VOLUME_DOWN
    VOLUME_MUTE = win32con.VK_VOLUME_MUTE
    MEDIA_NEXT_TRACK = win32con.VK_MEDIA_NEXT_TRACK
    MEDIA_PREV_TRACK = win32con.VK_MEDIA_PREV_TRACK
    MEDIA_PLAY_PAUSE = win32con.VK_MEDIA_PLAY_PAUSE
    BROWSER_BACK = win32con.VK_BROWSER_BACK
    BROWSER_FORWARD = win32con.VK_BROWSER_FORWARD


class Typeable(BaseTypeable):

    __slots__ = ("_code", "_modifiers", "_name", "_is_text", "_char")

    def __init__(self, code, modifiers=(), name=None, is_text=False):
        super(Typeable, self).__init__(code, modifiers, name, is_text)
        if not is_text and isinstance(code, string_types):
            self._char = code
        else:
            self._char = None

    @contextmanager
    def _set_keycode_and_modifiers(self):
        # Only required if this is a hardware-input lookup key.
        char, is_text = self._char, self._is_text
        if char is None or is_text:
            yield
            return
        code, modifiers = Keyboard.get_keycode_and_modifiers(char)
        # try:
        #     code, modifiers = Keyboard.get_keycode_and_modifiers(char)
        # except ValueError:
        #     # Fallback on the Unicode events if the key cannot be typed
        #     # using the current keyboard layout.
        #     code, modifiers = char, ()
        #     self._is_text = True

        # Set keycode and modifiers and yield.
        self._code, self._modifiers = code, modifiers
        try:
            yield
        finally:
            # Set _is_text back to the original value.
            self._is_text = is_text

    def on_events(self, timeout=0):
        with self._set_keycode_and_modifiers():
            return super(Typeable, self).on_events(timeout)

    def off_events(self, timeout=0):
        with self._set_keycode_and_modifiers():
            return super(Typeable, self).off_events(timeout)

    def events(self, timeout=0):
        with self._set_keycode_and_modifiers():
            return super(Typeable, self).events(timeout)


class Keyboard(BaseKeyboard):
    """Static class wrapper around SendInput."""

    shift_code = win32con.VK_SHIFT
    ctrl_code = win32con.VK_CONTROL
    alt_code = win32con.VK_MENU

    @classmethod
    def send_keyboard_events(cls, events):
        """
        Send a sequence of keyboard events.

        Positional arguments:
        events -- a sequence of tuples of the form
            (keycode, down, timeout), where
                keycode (int): Win32 Virtual Key code.
                down (boolean): True means the key will be pressed down,
                    False means the key will be released.
                timeout (int): number of seconds to sleep after
                    the keyboard event.
            or
            (character, down, timeout, is_text), where
                character (str): Unicode character.
                down (boolean): True means the key will be pressed down,
                    False means the key will be released.
                timeout (int): number of seconds to sleep after
                    the keyboard event.
                is_text (boolean): True means that the keypress is targeted
                    at a window or control that accepts Unicode text.
        """
        # Get the current window's keyboard layout.
        thread_id = win32process.GetWindowThreadProcessId(
            win32gui.GetForegroundWindow()
        )[0]
        layout = windll.user32.GetKeyboardLayout(thread_id)

        # Process and send keyboard events.
        items = []
        for event in events:
            if len(event) == 3:
                keycode, down, timeout = event
                input_structure = KeyboardInput(keycode, down,
                                                layout=layout)
            elif len(event) == 4 and event[3]:
                character, down, timeout = event[:3]
                input_structure = KeyboardInput(0, down, scancode=character)
            items.append(input_structure)
            if timeout:
                array = make_input_array(items)
                items = []
                send_input_array(array)
                time.sleep(timeout)
        if items:
            array = make_input_array(items)
            send_input_array(array)
            if timeout: time.sleep(timeout)

    @classmethod
    def _get_initial_keycode(cls, char):
        thread_id = win32process.GetWindowThreadProcessId(
            win32gui.GetForegroundWindow()
        )[0]
        layout = windll.user32.GetKeyboardLayout(thread_id)
        if isinstance(char, binary_type):
            char = char.decode(getpreferredencoding())

        # Get the code for this character.
        code = win32api.VkKeyScanEx(char, layout)
        if code == -1:
            raise ValueError("Unknown char: %r" % char)
        return code

    @classmethod
    def xget_virtual_keycode(cls, char):
        code = cls._get_initial_keycode(char)

        # Construct a list of the virtual key code and modifiers.
        codes = [code & 0x00ff]
        if code & 0x0100: codes.append(cls.shift_code)
        if code & 0x0200: codes.append(cls.ctrl_code)
        if code & 0x0400: codes.append(cls.alt_code)
        return codes

    @classmethod
    def get_keycode_and_modifiers(cls, char):
        code = cls._get_initial_keycode(char)

        # Construct a list of the virtual key code and modifiers.
        modifiers = []
        if code & 0x0100: modifiers.append(cls.shift_code)
        if code & 0x0200: modifiers.append(cls.ctrl_code)
        if code & 0x0400: modifiers.append(cls.alt_code)
        code &= 0x00ff
        return code, modifiers

    @classmethod
    def get_typeable(cls, char, is_text=False):
        if is_text:
            return Typeable(char, is_text=True)
        return Typeable(char, name=char)
