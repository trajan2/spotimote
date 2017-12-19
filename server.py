from __future__ import print_function

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

import webbrowser
import simplejson
import os
import time
import cherrypy
import sys
import argparse
import socket


class Spotimote:
    def __init__(self, username, password,
                 playlist="https://open.spotify.com/user/fragect6/playlist/6olBokeXVAmXOS03sE6GKP"):
        self.driver = webdriver.Chrome()
        self.driver.get(playlist)
        button = self.driver.find_element_by_id("has-account")
        button.click()

        time.sleep(1)  # wait .5 seconds till loaded

        username_elem = self.driver.find_element_by_id("login-username")
        password_elem = self.driver.find_element_by_id("login-password")
        username_elem.send_keys(username)
        password_elem.send_keys(password)
        username_elem.send_keys(Keys.RETURN)

    def retrieve_list(self, attributes):
        try:  # wait until playlist is visible
            element_present = EC.presence_of_element_located((By.CSS_SELECTOR, attributes[0][2]))
            WebDriverWait(self.driver, 5).until(element_present)
        except TimeoutException:
            print("Timeout, couldn't load list")
            return {att: [] for att in attributes}

        return {att: [{field: ele.get_attribute(field) for field in fields}
                      for ele in self.driver.find_elements_by_css_selector(css)
                      ] for att, fields, css in attributes}

    def play(self, number):
        """play a song from a playable list"""
        trackdiv = self.driver.find_elements_by_class_name("tracklist-row")[number]

        # scroll to title (so it is not covered by advertisement)
        self.driver.execute_script("arguments[0].scrollIntoView(true);", trackdiv)

        try:  # mouse over event
            hover = ActionChains(self.driver).move_to_element(trackdiv)
        except IndexError:
            return False
        hover.perform()
        #time.sleep(1)
        # input("hey")
        try:
            trackdiv.find_element_by_class_name("icon-play").click()
        except NoSuchElementException:
            trackdiv.find_element_by_class_name("icon-pause").click()
        except TimeoutException:
            print("couldn't start song")
            return False

        return True

    def is_playing(self):
        try:
            self.driver.find_element_by_css_selector(
                "button.control-button.spoticon-pause-16.control-button--circled")
        except NoSuchElementException:
            return False
        return True

    def click_button(self, action):
        buttons = {
            "shuffle": self.driver.find_element_by_css_selector("button.control-button.spoticon-shuffle-16"),
            "back": self.driver.find_element_by_css_selector("button.control-button.spoticon-skip-back-16"),
            "forward": self.driver.find_element_by_css_selector("button.control-button.spoticon-skip-forward-16"),
            "repeat": self.driver.find_element_by_css_selector("button.control-button.spoticon-repeat-16")}
        try:
            buttons["playpause"] = self.driver.find_element_by_css_selector(
                "button.control-button.spoticon-pause-16.control-button--circled")
        except NoSuchElementException:
            buttons["playpause"] = self.driver.find_element_by_css_selector(
                "button.control-button.spoticon-play-16.control-button--circled")
        buttons[action].click()

    def get(self, url=None):
        if url:
            self.driver.get(url)
            time.sleep(.5)  # TODO: implement real waiting

    def get_song_playing(self):
        return ""

    def get_search_term(self, type=None):
        selector = {
            "albums": ("inputBox-input", "value"),
            "playlists": ("inputBox-input", "value"),
            "artists": ("inputBox-input", "value"),
            "songs": ("inputBox-input", "value"),

            "album": ("header  div.media-bd div h2", "innerHTML"),
            "user": ("header  div.media-bd div h2", "innerHTML"),
            "artist": ("header h1", "innerHTML"),
        }

        if not type:
            type = self.get_type()
        try:
            return self.driver.find_element_by_css_selector(selector[type][0]).get_attribute(selector[type][1])
        except NoSuchElementException:
            return False

    def close(self):
        self.driver.close()

    def get_type(self):
        if "search/playlists" in self.driver.current_url:
            return "playlists"
        if "search/songs" in self.driver.current_url:
            return "songs"
        if "search/albums" in self.driver.current_url:
            return "albums"
        if "search/artists" in self.driver.current_url:
            return "artists"
        if "user" in self.driver.current_url:
            return "user"
        if "album" in self.driver.current_url:
            return "album"
        if "artist" in self.driver.current_url:
            return "artist"


class Server(object):
    @cherrypy.expose
    def index(self):
        return open(os.path.join(MEDIA_DIR, u'index.html'))

    @cherrypy.expose
    def action(self, action=""):
        cherrypy.response.headers['Content-Type'] = 'application/json'
        spotimote.click_button(action)
        return simplejson.dumps({
            "is_playing": spotimote.is_playing(),
            "title": spotimote.get_song_playing()
        }).encode('utf8')

    @cherrypy.expose
    def play(self, number):
        cherrypy.response.headers['Content-Type'] = 'application/json'
        succ = spotimote.play(int(number))
        return simplejson.dumps({"success": succ}).encode("utf8")

    @cherrypy.expose
    def list(self, url=None):
        spotimote.get(url)
        cherrypy.response.headers['Content-Type'] = 'application/json'
        type = spotimote.get_type()
        attributes = {
            "playlists": [
                ["playlist", ["innerHTML", "href"], "div.media-object-hoverable div div.react-contextmenu-wrapper a"],
                ["user", ["innerHTML", "href"], "div.media-object div.mo-meta span a"]],
            "artists": [
                ["artist", ["innerHTML", "href"], "div.media-object-hoverable div.mo-info div a"]],
            "albums": [
                ["album", ["innerHTML", "href"], "div.media-object div div.mo-info  div a"],
                # TODO: some albums have "various artist and thus a different sturcutre("artist", []]]
            ],
            "songs": [
                ["song", ["innerHTML"], ".tracklist-name"],
                ["artist", ["innerHTML", "href"], "span.artists-album :first-child :first-child a"]],
            "user": [
                ["song", ["innerHTML"], ".tracklist-name"],
                ["artist", ["innerHTML", "href"], "span.artists-album :first-child :first-child a"]],
            "artist": [
                ["song", ["innerHTML"], "span.tracklist-name"]],
            "album": [
                ["song", ["innerHTML"], "span.tracklist-name"]]
        }

        list_json = {"type": type, "title": spotimote.get_search_term(),
                     "list": spotimote.retrieve_list(attributes[type])}
        print(list_json)
        return simplejson.dumps(list_json).encode('utf8')


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


if __name__ == "__main__":
    MEDIA_DIR = os.path.join(os.path.abspath("."), u"media")

    parser = argparse.ArgumentParser()
    parser.add_argument('username', help='Spotify user name')
    parser.add_argument('password', help='Spotify password')
    args = parser.parse_args()

    ip = get_ip()
    port = 8080
    spotimote = Spotimote(args.username, args.password)
    cherrypy.engine.subscribe('start', lambda: webbrowser.open("http://"+ip+":"+str(port)+"/"))
    cherrypy.tree.mount(Server(), '/', config={
        '/media': {'tools.staticdir.on': True, 'tools.staticdir.dir': MEDIA_DIR},
        'global': {'server.socket_host': '0.0.0.0', 'server.socket_port': port}
        })
    cherrypy.config.update({'server.socket_host': ip, 'server.socket_port': port})
    try:
        cherrypy.engine.start()
    except KeyboardInterrupt:
        print("Exiting Spotimote")
        spotimote.close()
        sys.exit()
