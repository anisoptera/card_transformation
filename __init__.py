# -*- coding: utf-8 -*-
from __future__ import print_function
# import the main window object (mw) from aqt
from aqt import mw
# import the "show info" tool from utils.py
from aqt.utils import showInfo, askUser
# import all of the Qt GUI library
from aqt.qt import *
from anki.hooks import addHook, remHook
from anki.utils import intTime
import sys
import re


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

#======================================================================#
#= Configuration handling                                             =#
#======================================================================#

_config = None
def get_opt(option_name):
    global _config
    if _config is None:
        _config = mw.addonManager.getConfig(__name__)
    return _config[option_name]

# Deck which will have cards replaced from source deck preserving order
def get_ordering_deck(): return get_opt("OrderingDeck")
# Deck which will have cards pulled out of it
def get_source_deck(): return get_opt("SourceDeck")
# Enable automatic flagging (coloration) of cards as they are processed.
def get_flagging_enabled(): return get_opt("Flagging")
# Enable reloading menu option and hotkey for development
def get_reload_enabled(): return get_opt("ReloadButtonEnabled")

#======================================================================#

# this is either a really cool hack or a nightmare. you decide!
try: last_ordering_card = last_ordering_card or None
except NameError: last_ordering_card = None


def replace_note(ordering_note, replacing_note):
    target_deck = mw.col.decks.id(get_ordering_deck())
    ordering = ordering_note['Entry Number']

    replacing_note['Optimized-Voc-Index'] = ordering
    replacing_note.flush()
    mw.checkpoint(_("Replace Note"))
    mod = intTime()
    usn = mw.col.usn()
    mw.col.db.execute("""
update cards set usn=?, mod=?, did=? where id = ?""",
                      usn, mod, target_deck, replacing_note.id)

    mw.col.remNotes([ordering_note.id])
    mw.progress.finish()
    mw.reset()

def set_flag_for_cards_in_note(note, flag, only_unflagged=False):
    "Changes the flag on all cards for a note, or only for those which are not already flagged"
    card_ids_to_flag = []
    for c in note.cards():
        if (not only_unflagged) or c.userFlag() == 0:
            card_ids_to_flag.append(c.id)
    if card_ids_to_flag:
        mw.col.setUserFlag(flag, card_ids_to_flag)
    # browser.model.reset() seems needed for flagging to take effect; call it after batches of this


def search_ordering_card(browser):
    notes = browser.selectedNotes()
    for note in map(mw.col.getNote, notes):
        global last_ordering_card
        last_ordering_card = note

        try: front = last_ordering_card['Front']
        except: continue # Don't throw an error when a non-KLC card type is encountered
        queries = [front]

        # Remove する
        no_suru = re.sub(r"する$", "*", front)
        if front != no_suru:
            queries.append(no_suru)

        # Remove leading and trailing hiragana
        lead_hiragana_re = r'^[ぁ-ゔ]+'
        post_hiragana_re = r'[ぁ-ゔ]+$'

        hstripped = re.sub(lead_hiragana_re, "*", re.sub(post_hiragana_re, "*", front))
        if front != hstripped:
            queries.append(hstripped)

        # whatever card is selected
        for search_param in queries:
            query = "deck:'{}' Vocabulary-Kanji:{}".format(get_source_deck(), search_param)
            other_notes = mw.col.findNotes(query)
            if len(other_notes) == 0:
                # showInfo("No cards for query {}".format(query))
                if get_flagging_enabled(): set_flag_for_cards_in_note(note, 3)
                continue
            if len(other_notes) == 1:
                other = mw.col.getNote(other_notes[0])
                response = askUser("Single match detected: {} = {}, \n{} =? {}\nReplace?".format(
                    last_ordering_card['Front'], other['Vocabulary-Kanji'], last_ordering_card['Meaning'], other['Vocabulary-English']))
                if response:
                    if get_flagging_enabled(): set_flag_for_cards_in_note(other, 4)
                    replace_note(last_ordering_card, other)
                    break
                else:
                    continue

            if get_flagging_enabled(): set_flag_for_cards_in_note(last_ordering_card, 2)

            browser._lastSearchTxt = query
            browser.search()
            showInfo("Find match for {},\n{}".format(last_ordering_card['Front'], last_ordering_card['Meaning']))
            return
    if get_flagging_enabled(): browser.model.reset()

    # search for it in hardcoded db
    # possibly automate transforms


def confirm_matching_card(browser):
    assert(len(browser.selectedNotes()) == 1)
    global last_ordering_card
    assert(last_ordering_card is not None)

    selected_note = browser.card.note()
    if get_flagging_enabled(): set_flag_for_cards_in_note(selected_note, 4)
    replace_note(last_ordering_card, selected_note)
    last_ordering_card = None
    browser._lastSearchTxt = "deck:current is:new"
    browser.search()

def reload_extension(browser):
    global _config
    _config = None
    from importlib import reload
    addonFolder = mw.pm.addonFolder()
    if addonFolder not in sys.path:
        sys.path.insert(0, addonFolder)
    import card_transformation
    reload(card_transformation)
    browser.model.reset()
    mw.reset()
    # Explicitly reinitialize the menu, so the user doesn't need to reopen the browser
    setup_menus(browser)

# clear previously bound actions if they remain, and initialize the cleanup list
try:
    for (item, action) in prev_actions:
        try: item.removeAction(action)
        except: pass
    prev_actions = []
except NameError: prev_actions = []
def setup_menus(obj):
    print(obj)
    item = obj.form.menu_Cards
    def register_action(*actArgs, trigger):
        "Automatically handles cleanup registration for reloading"
        action = item.addAction(*actArgs)
        prev_actions.append((item, action))
        action.triggered.connect(lambda _: trigger(obj))
        return action

    o_card = register_action("Use as ordering card", trigger=search_ordering_card)
    o_card.setShortcut(QKeySequence("Ctrl+Shift+O"))

    c_card = register_action("Confirm matching card", trigger=confirm_matching_card)

    if get_reload_enabled():
        rl_card = register_action("Reload Card_Transformer Extension", trigger=reload_extension)
        rl_card.setShortcut(QKeySequence("Ctrl+Shift+E"))

# clear previous menu hook to prevent duplicate menu items being added across browser sessions
try: remHook("browser.setupMenus", prev_menu_hook)
except NameError: prev_menu_hook = None
addHook("browser.setupMenus", setup_menus)
prev_menu_hook = setup_menus
