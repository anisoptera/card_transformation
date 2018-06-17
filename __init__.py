# -*- coding: utf-8 -*-
from __future__ import print_function
# import the main window object (mw) from aqt
from aqt import mw
# import the "show info" tool from utils.py
from aqt.utils import showInfo, askUser
# import all of the Qt GUI library
from aqt.qt import *
from anki.hooks import addHook
from anki.utils import intTime
import sys
import re


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


ORDERING_DECK = 'The Deck::KLC Important Vocab'
SRC_DECK = 'The Deck::Core 2k/6k Optimized Japanese Vocabulary'

# this is either a really cool hack or a nightmare. you decide!
last_ordering_card = None


def replace_note(ordering_note, replacing_note):
    target_deck = mw.col.decks.id(ORDERING_DECK)
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


def search_ordering_card(browser):
    notes = browser.selectedNotes()
    for note in map(mw.col.getNote, notes):
        global last_ordering_card
        last_ordering_card = note

        front = last_ordering_card['Front']
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
            query = "deck:'The Deck::Core 2k/6k Optimized Japanese Vocabulary' Vocabulary-Kanji:{}".format(search_param)
            other_notes = mw.col.findNotes(query)
            if len(other_notes) == 0:
                # showInfo("No cards for query {}".format(query))
                continue
            if len(other_notes) == 1:
                other = mw.col.getNote(other_notes[0])
                response = askUser("Single match detected: {} = {}, \n{} =? {}\nReplace?".format(
                    last_ordering_card['Front'], other['Vocabulary-Kanji'], last_ordering_card['Meaning'], other['Vocabulary-English']))
                if response:
                    replace_note(last_ordering_card, other)
                    break
                else:
                    continue

            browser._lastSearchTxt = query
            browser.search()
            showInfo("Find match for {},\n{}".format(last_ordering_card['Front'], last_ordering_card['Meaning']))
            return

    # search for it in hardcoded db
    # possibly automate transforms


def confirm_matching_card(browser):
    assert(len(browser.selectedNotes()) == 1)
    global last_ordering_card
    assert(last_ordering_card is not None)

    selected_note = browser.card.note()
    replace_note(last_ordering_card, selected_note)
    last_ordering_card = None
    browser._lastSearchTxt = "deck:current is:new"
    browser.search()


def setup_menus(obj):
    print(obj)
    item = obj.form.menu_Cards
    o_card = item.addAction("Use as ordering card")
    o_card.setShortcut(QKeySequence("Ctrl+Shift+O"))
    o_card.triggered.connect(lambda x: search_ordering_card(obj))

    c_card = item.addAction("Confirm matching card")
    c_card.triggered.connect(lambda x: confirm_matching_card(obj))


addHook("browser.setupMenus", setup_menus)
