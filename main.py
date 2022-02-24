import threading
import time
import bs4
import requests
import StellarPlayer
import re
import urllib.parse

cilixiong_home = 'https://www.cilixiong.com/'

def concatUrl(url1, url2):
    if url2.startswith('http'):
        return url2
    splits = re.split(r'/+',url1)
    url = splits[0] + '//'
    if url2.startswith('/'):
        url = url + splits[1] + url2
    else:
        url = url + '/'.join(splits[1:-1]) + '/' + url2
    return url

def parse_cilixiong_category():
    res = requests.get(cilixiong_home,verify=False)
    category = []
    blacks = ['留言','关于','在线看','搜索']
    if res.status_code == 200:
        bs = bs4.BeautifulSoup(res.content, 'html.parser')
        selector = bs.select('#menu2 > div > div > div.col-md-8 > div li')
        for item in selector:
            url = item.select('a')[0].get('href')
            title = item.select('a')[0].text
            if title not in blacks:
                category.append({'url':concatUrl(cilixiong_home,url),'title':title})
        print(category)
    return category,['https://www.cilixiong.com/e/search/index.php']

def parse_cilixiong_page_num(catUrl,catName):
    if catName == '首页':
        return ['']
    res = requests.get(catUrl,verify=False)
    pages = []
    if res.status_code == 200:
        bs = bs4.BeautifulSoup(res.content,'html.parser')
        selector = bs.select('body > div.main-container > section > div.container > div > div > div.text-center > ul a')
        if len(selector) > 0:
            last = selector[-1]
            url = last.get('href')
            m = re.match(catUrl+"index_(\d+).(\w+)", url)
            if m:
                num = int(m.group(1))
                pages.append(f'index.{m.group(2)}')
                pages += [f'index_{i}.{m.group(2)}' for i in range(2,num + 1)]
    return pages

def parse_cilixiong_page_movies(url):
    res = requests.get(url,verify=False)
    movies = []
    if res.status_code == 200:
        bs = bs4.BeautifulSoup(res.content, 'html.parser')
        selector = bs.select('body > div.main-container > section.imagebg.bg--dark > div > div > div.col-sm-12.text-center > div > div  a')
        for item in selector:
            url = item.get('href')
            img = item.select('img')[0].get('src')
            title = item.select('h5')[0].next
            score = item.select('em')[0].text
            movies.append({'url':url,'img':img,'title':title,'score':score})
    return movies

def search_cilixiong_page_movies(search_url,search_word):
    movies = []
    res = requests.post(search_url,data={'show':'title','keyboard':search_word,'classid':'1,2'},verify=False)
    print(res.content)
    if res.status_code == 200:
        bs = bs4.BeautifulSoup(res.content,'html.parser')
        selector = bs.select('body > div.main-container > section > div.container > div.row > div a')
        for item in selector:
            url = item.get('href')
            img = item.select('img')[0].get('src')
            title = item.select('h5')[0].next
            score = item.select('em')[0].text
            movies.append({'url':url,'img':img,'title':title,'score':score})
    return movies

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def parse_cilixiong_movie(url):
    res = requests.get(url,verify=False)
    movies = []
    if res.status_code == 200:
        bs = bs4.BeautifulSoup(res.content, 'html.parser')
        selector = bs.select('body > section > div > div > div > div > div.tab__content > div > div div')
        for item in chunks(selector, 3):
            title = item[0].string
            url = item[1].select('a')[0].get('href')
            movies.append({'title':title,'url':url})
        print(movies)
    return movies

class m66ysplugin(StellarPlayer.IStellarPlayerPlugin):
    def __init__(self,player:StellarPlayer.IStellarPlayer):
        super().__init__(player)
        self.categories = []
        self.search_urls = []
        self.pages = []
        self.movies = []
        self.pageIndex = 0
        self.curCategory = ''
        self.curCategoryName = ''
        self.cur_page = '第' + str(self.pageIndex + 1) + '页'
        self.num_page = ''
        self.search_word = ''
        self.search_movies = []
        self.movie_urls = {}
        self.gbthread = threading.Thread(target=self._bgThread)


    def _bgThread(self):
        while len(self.categories) == 0 and not self.isExit:
            self.parsePage()
            time.sleep(0.001)
        print(f'66ys bg thread:{self.gbthread.native_id} exit')
        # 刷新界面
        def update():
            if self.player.isModalExist('main'):
                self.updateLayout('main',self.makeLayout())
                self.loading(True)
        if hasattr(self.player,'queueTask'):
            self.player.queueTask(update)
        else:
            update()
       
    def stop(self):
        if self.gbthread.is_alive():
            print(f'66ys bg thread:{self.gbthread.native_id} is still running')
        return super().stop()

    def start(self):
        self.gbthread.start()
        return super().start()

    def parsePage(self):
        #获取分类导航
        if len(self.categories) == 0:
            self.categories, self.search_urls = parse_cilixiong_category()
        if len(self.categories) > 0:
            if not self.curCategory:
                self.curCategory, self.curCategoryName = self.categories[0]['url'],self.categories[0]['title']
            #获取该分类的所有页面数
            if len(self.pages) == 0:
                self.pages = parse_cilixiong_page_num(self.curCategory, self.curCategoryName)
                self.num_page = '共' + str(len(self.pages)) + '页'
                if len(self.pages) > 0:
                    #获取分页视频资源
                    if len(self.movies) == 0:
                        url = concatUrl(self.curCategory, self.pages[self.pageIndex])
                        self.movies = parse_cilixiong_page_movies(url)  

    def makeLayout(self):
        nav_labels = []
        for cat in self.categories:
            nav_labels.append({'type':'link','name':cat['title'],'@click':'onCategoryClick','width':60})

        grid_layout = {'group':
                            [
                                {'type':'image','name':'img','width':120,'height':150,'@click':'onMovieImageClick'},
                                {'type':'label','name':'title','hAlign':'center'},
                            ],
                            'dir':'vertical'
                      }
        controls = [
            {'group':nav_labels,'height':30},
            {'type':'space','height':10},
            {'group':
                [
                    {'type':'edit','name':'search_edit','label':'搜索'},
                    {'type':'button','name':'搜电影','@click':'onSearch'}
                ]
                ,'height':30
            },
            {'type':'space','height':10},
            {'type':'grid','name':'list','itemlayout':grid_layout,'value':self.movies,'marginSize':5,'itemheight':180,'itemwidth':120},
            {'group':
                [
                    {'type':'space'},
                    {'group':
                        [
                            {'type':'label','name':'cur_page',':value':'cur_page'},
                            {'type':'link','name':'上一页','@click':'onClickFormerPage'},
                            {'type':'link','name':'下一页','@click':'onClickNextPage'},
                            {'type':'link','name':'首页','@click':'onClickFirstPage'},
                            {'type':'link','name':'末页','@click':'onClickLastPage'},
                            {'type':'label','name':'num_page',':value':'num_page'},
                        ]
                        ,'width':0.45
                        ,'hAlign':'center'
                    },
                    {'type':'space'}
                ]
                ,'height':30
            },
            {'type':'space','height':5}
        ]
        return controls
        
    def show(self):
        controls = self.makeLayout()
        self.doModal('main',800,600,'',controls)

    def onModalCreated(self, pageId):
        print(f'dytt onModalCreated {pageId=}')
        if pageId == 'main':
            if len(self.movies) == 0:
                self.loading()

    def onSearchInput(self,*args):
        print(f'{self.search_word}')

    def onSearch(self,*args):
        self.search_word = self.player.getControlValue('main','search_edit')
        if len(self.search_urls) > 0:
            url = self.search_urls[0]
            self.loading()
            self.search_movies = search_cilixiong_page_movies(url,self.search_word)
            self.loading(stopLoading=True)
            print(self.search_movies)
            if len(self.search_movies) > 0:
                grid_layout = {'group':
                            [
                                {'type':'image','name':'img','width':120,'height':150,'@click':'onMovieImageClick'},
                                {'type':'label','name':'title','hAlign':'center'},
                            ],
                            'dir':'vertical'
                      }
                controls = {'type':'grid','name':'list','itemlayout':grid_layout,'value':self.search_movies,'marginSize':5,'itemheight':180,'itemwidth':120}
                if not self.player.isModalExist('search'):
                    self.doModal('search',800,600,self.search_word,controls)
                else:
                    self.player.updateControlValue('search','list',self.search_movies)
            else:
                self.player.toast('main',f'没有找到 {self.search_word} 相关的资源')
    

    def onCategoryClick(self,pageId,control,*args):
        for cat in self.categories:
            if cat['title'] == control:
                if cat['url'] != self.curCategory:
                    self.curCategory, self.curCategoryName = cat['url'], cat['title']
                    self.pageIndex = 0
                    #获取新分类的页面数
                    self.loading()
                    self.pages = parse_cilixiong_page_num(self.curCategory, self.curCategoryName)
                    self.num_page = num_page = '共' + str(len(self.pages)) + '页'
                    self.player.updateControlValue('main','num_page',num_page)
                    self.selectPage()
                    self.loading(True)
                break
        
    def onMovieImageClick(self, pageId, control, item, *args):
        movie_name = ''
        self.loadingPage(pageId)
        if pageId == 'main':
            playUrl = parse_cilixiong_movie(self.movies[item]['url'])
            movie_name = self.movies[item]['title']
        elif pageId == 'search':
            playUrl = parse_cilixiong_movie(self.search_movies[item]['url'])
            movie_name = self.search_movies[item]['title']
        if len(playUrl) > 0:
            list_layout = [{'type':'label','name':'title','fontSize':12}, {'type':'link','name':'播放','width':30,'@click':'onPlayClick'}]
            if hasattr(self.player,'download'):
                list_layout.append({'type':'space','width':10})
                list_layout.append({'type':'link','name':'下载','width':30,'@click':'onDownloadClick'})
            layout = {'type':'list','name':'list','itemlayout':{'group':list_layout},'value':playUrl,'separator':True,'itemheight':30}
            self.movie_urls[movie_name] = playUrl
            self.loadingPage(pageId,stopLoading=True)
            self.doModal(movie_name, 600, 500, movie_name, layout)
            self.movie_urls.pop(movie_name)
        else:
            self.loadingPage(pageId,stopLoading=True)
            self.player.toast('main','无可播放源')

    def onPlayClick(self, pageId, control, item, *args):
        if pageId in self.movie_urls:
            self.player.play(self.movie_urls[pageId][item]['url'])
    
    def onDownloadClick(self, pageId, control, item, *args):
        if pageId in self.movie_urls:
            self.player.download(self.movie_urls[pageId][item]['url'])

    def selectPage(self):
        if len(self.pages) > self.pageIndex:
                self.movies.clear()
                self.player.updateControlValue('main','list',self.movies)
                url = concatUrl(self.curCategory, self.pages[self.pageIndex])
                self.movies = parse_cilixiong_page_movies(url)
                self.player.updateControlValue('main','list',self.movies)
                self.cur_page = page = '第' + str(self.pageIndex + 1) + '页'
                self.player.updateControlValue('main','cur_page',page)

    def onClickFormerPage(self, *args):
        if self.pageIndex > 0:
            self.pageIndex = self.pageIndex - 1
            self.loading()
            self.selectPage()
            self.loading(True)

    def onClickNextPage(self, *args):
        num_page = len(self.pages)
        if self.pageIndex + 1 < num_page:
            self.pageIndex = self.pageIndex + 1
            self.loading()
            self.selectPage()
            self.loading(True)

    def onClickFirstPage(self, *args):
        if self.pageIndex != 0:
            self.pageIndex = 0
            self.loading()
            self.selectPage()
            self.loading(True)

    def onClickLastPage(self, *args):
        if self.pageIndex != len(self.pages) - 1:
            self.pageIndex = len(self.pages) - 1
            self.loading()
            self.selectPage()
            self.loading(True)

    def loading(self, stopLoading = False):
        if hasattr(self.player,'loadingAnimation'):
            self.player.loadingAnimation('main', stop=stopLoading)

    def loadingPage(self, page, stopLoading = False):
        if hasattr(self.player,'loadingAnimation'):
            self.player.loadingAnimation(page, stop=stopLoading)

    def onPlayerSearch(self, dispatchId, searchId, wd, limit):
        # 播放器搜索异步接口
        print(f'onPlayerSearch:{wd}')
        result = []
        url = 'https://www.cilixiong.com/e/search/index.php'
        if len(self.search_urls) > 0:
            url = self.search_urls[0]
        movies = search_cilixiong_page_movies(url,wd)
        for item in movies:
            magnets = parse_cilixiong_movie(item['url'])
            if len(magnets) > 0:
                urls = []
                index = 1
                for magnet in magnets:
                    obj = []
                    obj.append('磁力' + str(index))
                    obj.append(magnet['url'])
                    urls.append(obj)
                    index = index + 1
                result.append({'urls':urls,'name':item['title'],'pic':item['img']})
            if len(result) >= limit:
                break
        self.player.dispatchResult(dispatchId, searchId=searchId, wd=wd, result=result)
    
def newPlugin(player:StellarPlayer.IStellarPlayer,*arg):
    plugin = m66ysplugin(player)
    return plugin

def destroyPlugin(plugin:StellarPlayer.IStellarPlayerPlugin):
    plugin.stop()
