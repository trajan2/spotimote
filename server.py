from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import selenium
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

    def get_div_list(self, class_name="tracklist-row"):
        return self.driver.find_elements_by_class_name(class_name)

    def show_playlist(self, attributes=None):
        if attributes is None:
            attributes = {"song": "tracklist-name", "artist": "link-subtle"}
        return [{att: div.find_element_by_class_name(cls).get_attribute("innerHTML")
                 for att, cls in attributes.items()} for div in self.get_div_list()]

    def play(self, number):
        trackdiv_list = self.get_div_list()
        try:
            hover = ActionChains(self.driver).move_to_element(trackdiv_list[number])
        except IndexError:
            return False
        hover.perform()
        time.sleep(1)
        try:
            trackdiv_list[number].find_element_by_class_name("icon-play").click()
        except selenium.common.exceptions.NoSuchElementException:
            trackdiv_list[number].find_element_by_class_name("icon-pause").click()
        return True

    def is_playing(self):
        try:
            self.driver.find_element_by_css_selector(
                "button.control-button.spoticon-pause-16.control-button--circled")
        except selenium.common.exceptions.NoSuchElementException:
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
        except selenium.common.exceptions.NoSuchElementException:
            buttons["playpause"] = self.driver.find_element_by_css_selector(
                "button.control-button.spoticon-play-16.control-button--circled")
        buttons[action].click()

    def get(self, url=None):
        if url:
            self.driver.get(url)
            time.sleep(2) #TODO: implement real waiting

    def get_title(self):
        return ""

    def close(self):
        self.driver.close()


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
            "title": spotimote.get_title()
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
        if "playlist" in spotimote.driver.current_url:
            list_json = {"type": "user", "list": spotimote.show_playlist(), "title": "User Playlist"}
        elif "songs" in spotimote.driver.current_url:
            list_json = {"type": "songs", "list": spotimote.show_playlist(), "title": "Search Track"}
            #print(driver.show_playlist())
        else:
            list_json = {}
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
