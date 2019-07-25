#!/usr/bin/env python
# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import threading
import csv
import os
import gzip
import requests
import io
import re
import redis
import socket
# import logging
import coloredlogs, logging
from termcolor import colored


# logging.basicConfig(level=logging.INFO)


class RequestHandler(BaseHTTPRequestHandler):
     
    def handle_one_request(self):
        """Handle a single HTTP request.
 
        You normally don't need to override this method; see the class
        __doc__ string for information on how to handle specific HTTP
        commands such as GET and POST.
 
        """
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.requestline = ''
                self.request_version = ''
                self.command = ''
                self.send_error(414)
                return
            if not self.raw_requestline:
                self.close_connection = 1
                return
            if not self.parse_request():
                # An error code has been sent, just exit
                return
            mname = 'do_' + self.command
            if not hasattr(self, mname):
                self.send_error(501, "Unsupported method (%r)" % self.command)
                return
            method = getattr(self, mname)
            method()
            if not self.wfile.closed:
                self.wfile.flush() 
        except socket.timeout as e:
            self.log_error("Request timed out: %r", e)
            self.close_connection = 1
            return





F_LIST_LOCK = threading.Lock()
TEMP_SUFFIX = '.temp'
CONTENT_ENC = 'content-encoding'
TRANSFER_ENC = 'transfer-encoding'
CONTENT_LEN = 'content-length'
ACCESS_CONTROL_ALLOW = 'access-control-allow-origin'
host = "127.0.0.1"
port = 6379
pool = redis.ConnectionPool(host=host, port=port)
redis_c = redis.Redis(connection_pool=pool)
fetch_count = 0
post_count = 0
local_res_conut = 0

def write_file(path, data, url, url_list_path, code):
    logging.debug("I am writing file.")

    temp_path = path + TEMP_SUFFIX
    if os.path.exists(path) or os.path.exists(temp_path):
        # print("The file is exist.")
        # print("This file size is : ",os.path.getsize(temp_path))
        if os.path.getsize(temp_path) == 0:
            logging.debug("Remove this file.")
            os.remove(temp_path)
        else:
            logging.debug("This file size if not 0. Something wrong.")
            return
    if code == 304:
        # print("This file is in your cache.")
        return


    cache_dir = os.path.dirname(path)
    if not os.path.exists(cache_dir):
        try:
            os.makedirs(cache_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    with open(temp_path, 'wb') as f:
        f.write(data)

    if os.path.getsize(temp_path) == 0:
        logging.debug('Got zero byte cache file: {0}'.format(url))
        return

    os.rename(temp_path, path)

    if os.stat(path).st_size == 0:
        logging.error("I finish writing file. But the file size is 0.")
        logging.error('Bad file size: {0}'.format(path))
        os.remove(path)

    redis_c.set(os.path.basename(path),url)
    # print('redis: ',redis_c.get(os.path.basename(path)))
    logging.info('Updating cache')
    # logging.info('Updating cache list: {0}'.format(url_list_path))

    # logging.info('Updating cache list: {0}'.format(url_list_path))
    # F_LIST_LOCK.acquire()
    # with open(url_list_path, 'a') as csvf:
    #     w = csv.writer(csvf, quoting=csv.QUOTE_ALL)
    #     w.writerow([os.path.basename(path), url, len(data)])
    # F_LIST_LOCK.release()


def gbf_caching_handler_factory(gbf_conf, executor, uri_matcher,
    headers_matcher, cache_namer):

    class GBFCachingHandler(RequestHandler):
        CACHE_DIR = None
        CACHE_LIST_PATH = None
        CACHE_NAMER = None
        EXECUTOR = None
        URI_MATCHER = None
        HEADERS_MATCHER = None

        def __init__(self, *args, **kwargs):
            print("")
            print(colored("<<<<===================================================>>>>","green"))
            self.CACHE_DIR = gbf_conf.cache
            self.CACHE_LIST_PATH = os.path.join(gbf_conf.cache, '.cache_list')
            self.EXECUTOR = executor
            self.URI_MATCHER = uri_matcher
            self.HEADERS_MATCHER = headers_matcher
            self.CACHE_NAMER = cache_namer
            # print()
            super(GBFCachingHandler, self).__init__(*args, **kwargs)
            # print(self.headers)

        def _fetch_path(self):
            # print(colored("FETECHING","yellow"))
            # print("the path is : ",self.path)
            global fetch_count
            fetch_count = fetch_count + 1
            print(colored("I requeset remote server. count : ","red"), str(fetch_count))
            return requests.get(self.path, headers=self.headers)

        def _cache_data(self):
            print(colored(self.path,"cyan"))
            # print(self.check_url())
            if self.check_url():
                cache_filename = self.CACHE_NAMER.to_cache_name(self.path)
                cache_path = os.path.join(self.CACHE_DIR, cache_filename)
                # print("cache_filename is :",cache_filename)
                # print("cache_path is :",cache_path)
                response = None

                # print(os.path.exists(cache_path))

                # if cache_filename and os.path.exists(cache_path):
                #     # print("cache_filename is :",cache_filename)
                #     # print("cache_path is :",cache_path)
                #     print(colored("This request is in my server cache.","green"))
                #     logging.debug('Cache hit: {0} ({1})'.format(self.path,
                #         cache_path))
                #     with open(cache_path, 'rb') as f:
                #         data = f.read()
                #         response = requests.Response()
                #         setattr(response, 'status_code', 200)
                #         setattr(response, '_content', data)
                #         setattr(response, 'headers', {
                #             CONTENT_LEN: str(len(data)),
                #             CONTENT_ENC: 'identity',
                #             ACCESS_CONTROL_ALLOW: '*'

                #         })


                if cache_filename:
                    print("cache_filename is :",cache_filename)
                    print("cache_path is :",cache_path)
                    res = redis_c.get(cache_filename)
                    print("redis get res :",res)

                    if res and os.path.isfile(cache_path):
                        print(colored("This request file is in my server cache. I have lied myself.","green"))
                        global local_res_conut
                        local_res_conut = local_res_conut + 1
                        print(colored("local_res_conut : ","green"),local_res_conut)

                        # logging.debug('Cache hit: {0} ({1})'.format(self.path,
                        #     cache_path))
                        # if os.path.isfile(cache_path):
                        with open(cache_path, 'rb') as f:
                            data = f.read()
                            response = requests.Response()
                            # response.headers
                            setattr(response, 'status_code', 200)
                            setattr(response, '_content', data)
                            setattr(response, 'headers', {
                                CONTENT_LEN: str(len(data)),
                                CONTENT_ENC: 'identity',
                                # 'Cache-Control':'public, max-age=31536000, s-maxage=31536000',
                                'Cache-Control':'max-age=31536000',
                                # 'Cache-Control':'s-maxage=2592000',
                                ACCESS_CONTROL_ALLOW: '*'
                            })
                        # else:
                        #     print(colored("I got file in db, but the file is not exist","red"))

                    else:
                        # print(colored("I CANNOT find the file in my server cache.","yellow"))
                        # print(colored("Cache miss:","red"),colored("Cache miss: `````````````I will get the file from cdn.``````````````","yellow"))
                        response = self._fetch_path()
                        data = response.content
                        # print("The data file size is :",len(response.content))
                        headers = response.headers
                        status_code = response.status_code

                        

                        print("status code :",response.status_code)

                        if status_code == 200 :
                            # if cache_filename and self.HEADERS_MATCHER.matches(headers):
                            #     # logging.debug('Cache miss: {0}'.format(self.path))
                            #     fut = executor.submit(write_file, cache_path, data,
                            #         self.path, self.CACHE_LIST_PATH, status_code)

                            if cache_filename :
                                if self.HEADERS_MATCHER.matches(headers) == 'image':
                                    print("It is a image.")
                                    headers['Cache-Control'] = 'public, max-age=31536000, s-maxage=31536000',
                                    fut = executor.submit(write_file, cache_path, data,
                                        self.path, self.CACHE_LIST_PATH, status_code)
                                elif self.HEADERS_MATCHER.matches(headers) == 'image':
                                    print("It is a audio.")
                                    headers['Cache-Control'] = 'public, max-age=31536000, s-maxage=31536000',
                                    fut = executor.submit(write_file, cache_path, data,
                                        self.path, self.CACHE_LIST_PATH, status_code)
                                elif self.HEADERS_MATCHER.matches(headers) == 'javascript':
                                    headers['Cache-Control'] = 'public, max-age=604800, s-maxage=604800',
                                    print("It is a javascript.")
                                    fut = executor.submit(write_file, cache_path, data,
                                        self.path, self.CACHE_LIST_PATH, status_code)
                                elif self.HEADERS_MATCHER.matches(headers) == 'css':
                                    headers['Cache-Control'] = 'public, max-age=604800, s-maxage=604800',
                                    print("It is a css.")
                                    fut = executor.submit(write_file, cache_path, data,
                                        self.path, self.CACHE_LIST_PATH, status_code)


                                else:
                                    print(colored('It is not a image or audoi or javescript. do nothing','yellow'))



                        elif status_code == 304:
                            print(colored(".............I will get the file from the browser cache..............","green"))

                else:
                    print("I dont konw why no hash name.")


                return response

            else:
                print("This url is wrong.")
                response = None
                return response





        def check_host(self):

            pattern = re.compile(r'^(game|game-a[\d*]|game-a)\.granbluefantasy.jp$')
            match = pattern.match(self.headers['Host'])
            return match

            # pass


        def check_url(self):
            pattern = re.compile(r'^http:\/\/(game|game-a[\d*]|game-a)\.granbluefantasy.jp\/')
            match = pattern.match(self.path)
            return match
            
            # pass


        def do_GET(self):
            # print(colored("CALLING GET","yellow"))
            # print(self.headers['Host'])
            
            # print(self.check_host())
            # print(self.client_address[0])

            # logging.info('USER {0} GET '.format(self.client_address[0]))

            if self.check_host():
                logging.info('USER:{0}, GET:{1}'.format(self.client_address[0],self.path))
                if self.URI_MATCHER.matches(self.path):
                    print(colored('URI_MATCHER.matches true, _cache_data ',"blue"))
                    response = self._cache_data()
                else:
                    print(colored('URI_MATCHER.matches failed, _fetch_path ',"cyan"))
                    response = self._fetch_path()
                self.handle_response(response)
            else:
                response = None
                logging.critical('USER:{0}, GET:{1}'.format(self.client_address[0],self.path))
                print(colored("fxxk.","red"))
                self.handle_response(response)


        def do_POST(self):

            global post_count
            post_count = post_count + 1
            # print("")
            # print(colored('URI_MATCHER.matches failed, _fetch_path ',"cyan"))

            print(colored("I am CALLING POST. post_count :","red"),post_count)
            if self.check_host():
                # if self.URI_MATCHER.matches(self.path):
                #     print(colored('URI_MATCHER.matches true, _cache_data ',"blue"))
                #     response = self._cache_data()
                # else:
                #     print(colored('URI_MATCHER.matches failed, _fetch_path ',"cyan"))
                #     response = self._fetch_path()
                # self.handle_response(response)
                logging.info('USER:{0}, POST:{1}'.format(self.client_address[0],self.path))
                self.data = self.rfile.read(int(self.headers['Content-Length']))
                response = requests.post(self.path, headers=self.headers, data=self.data)
                self.handle_response(response)

            else:
                response = None
                logging.critical('USER:{0}, POST:{1}'.format(self.client_address[0],self.path))
                print(colored("fxxk.","red"))
                self.handle_response(response)






        def do_DELETE(self):
            self.data = self.rfile.read(int(self.headers['Content-Length']))

        def handle_response(self, response):
            if response.status_code < 400:
                self.send_response(response.status_code)
            else:
                self.send_error(response.status_code)

            output = response.content
            headers = response.headers

            # requests already decompressed gzip
            if CONTENT_ENC in headers and \
                    headers[CONTENT_ENC].lower() == 'gzip':
                headers[CONTENT_ENC] = 'identity'
                headers[CONTENT_LEN] = str(len(output))

            for k, v in headers.items():
                self.send_header(k, v)

            self.end_headers()
            self.wfile.write(output)

        def log_message(self, fmt, *args):
            pass

    return GBFCachingHandler
