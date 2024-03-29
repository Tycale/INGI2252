# The contents of this file are subject to the Common Public Attribution
# License Version 1.0. (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# http://code.reddit.com/LICENSE. The License is based on the Mozilla Public
# License Version 1.1, but Sections 14 and 15 have been added to cover use of
# software over a computer network and provide for limited attribution for the
# Original Developer. In addition, Exhibit A has been modified to be consistent
# with Exhibit B.
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License for
# the specific language governing rights and limitations under the License.
#
# The Original Code is reddit.
#
# The Original Developer is the Initial Developer.  The Initial Developer of
# the Original Code is reddit Inc.
#
# All portions of the code written by reddit are Copyright (c) 2006-2014 reddit
# Inc. All Rights Reserved.
###############################################################################

import hmac
import hashlib

from r2.models import *
from filters import unsafe, websafe, _force_unicode, _force_utf8
from r2.lib.utils import UrlParser, timeago, timesince, is_subdomain

from r2.lib import hooks
from r2.lib.static import static_mtime
from r2.lib import js

import babel.numbers
import simplejson
import os.path
from copy import copy
import random
import urlparse
import calendar
import math
import time
from pylons import g, c, request
from pylons.i18n import _, ungettext


static_text_extensions = {
    '.js': 'js',
    '.css': 'css',
    '.less': 'css'
}
def static(path):
    """
    Simple static file maintainer which automatically paths and
    versions files being served out of static.

    In the case of JS and CSS where g.uncompressedJS is set, the
    version of the file is set to be random to prevent caching and it
    mangles the path to point to the uncompressed versions.
    """
    dirname, filename = os.path.split(path)
    extension = os.path.splitext(filename)[1]
    is_text = extension in static_text_extensions
    should_cache_bust = False

    path_components = []
    actual_filename = None

    if g.static_domain:
        domain = g.static_domain
    else:
        path_components.append(c.site.static_path)

        if g.uncompressedJS:
            # unminified static files are in type-specific subdirectories
            if not dirname and is_text:
                path_components.append(static_text_extensions[extension])

            should_cache_bust = True
            actual_filename = filename

        domain = None

    path_components.append(dirname)
    if not actual_filename:
        actual_filename = g.static_names.get(filename, filename)
    path_components.append(actual_filename)

    actual_path = os.path.join(*path_components)

    query = None
    if path and should_cache_bust:
        file_id = static_mtime(actual_path) or random.randint(0, 1000000)
        query = 'v=' + str(file_id)

    return urlparse.urlunsplit((
        None,
        domain,
        actual_path,
        query,
        None
    ))


def make_url_protocol_relative(url):
    if not url:
        return url

    assert url.startswith("http://"), "make_url_protocol_relative: not http"
    return url[len("http:"):]


def media_https_if_secure(url):
    if not c.secure:
        return url
    return g.media_provider.convert_to_https(url)


def header_url(url):
    if url == g.default_header_url:
        return static(url)
    else:
        return media_https_if_secure(url)


def js_config(extra_config=None):
    logged = c.user_is_loggedin and c.user.name
    gold = bool(logged and c.user.gold)

    controller_name = request.environ['pylons.routes_dict']['controller']
    action_name = request.environ['pylons.routes_dict']['action']
    mac = hmac.new(g.secrets["action_name"], controller_name + '.' + action_name, hashlib.sha1)
    verification = mac.hexdigest()

    config = {
        # is the user logged in?
        "logged": logged,
        # the subreddit's name (for posts)
        "post_site": c.site.name if not c.default_sr else "",
        # the user's voting hash
        "modhash": c.modhash or False,
        # the current rendering style
        "renderstyle": c.render_style,

        # they're welcome to try to override this in the DOM because we just
        # disable the features server-side if applicable
        'store_visits': gold and c.user.pref_store_visits,

        # current domain
        "cur_domain": get_domain(cname=c.frameless_cname, subreddit=False, no_www=True),
        # where do ajax requests go?
        "ajax_domain": get_domain(cname=c.authorized_cname, subreddit=False),
        "stats_domain": g.stats_domain or '',
        "extension": c.extension,
        "https_endpoint": is_subdomain(request.host, g.domain) and g.https_endpoint,
        # does the client only want to communicate over HTTPS?
        "https_forced": c.user.https_forced,
        # debugging?
        "debug": g.debug,
        "send_logs": g.live_config["frontend_logging"],
        "server_time": math.floor(time.time()),
        "status_msg": {
          "fetching": _("fetching title..."),
          "submitting": _("submitting..."),
          "loading": _("loading...")
        },
        "is_fake": isinstance(c.site, FakeSubreddit),
        "adtracker_url": g.adtracker_url,
        "clicktracker_url": g.clicktracker_url,
        "uitracker_url": g.uitracker_url,
        "static_root": static(''),
        "over_18": bool(c.over18),
        "new_window": bool(c.user.pref_newwindow),
        "vote_hash": c.vote_hash,
        "gold": gold,
        "has_subscribed": logged and c.user.has_subscribed,
        "pageInfo": {
          "verification": verification,
          "actionName": controller_name + '.' + action_name,
        },
    }

    if g.uncompressedJS:
        config["uncompressedJS"] = True

    if extra_config:
        config.update(extra_config)

    hooks.get_hook("js_config").call(config=config)

    return config


class JSPreload(js.DataSource):
    def __init__(self, data=None):
        if data is None:
            data = {}
        js.DataSource.__init__(self, "r.preload.set({content})", data)

    def set(self, url, data):
        self.data[url] = data

    def set_wrapped(self, url, wrapped):
        from r2.lib.pages.things import wrap_things
        if not isinstance(wrapped, Wrapped):
            wrapped = wrap_things(wrapped)[0]
        self.data[url] = wrapped.render_nocache('api').finalize()

    def use(self):
        hooks.get_hook("js_preload.use").call(js_preload=self)

        if self.data:
            return js.DataSource.use(self)
        else:
            return ''


def class_dict():
    t_cls = [Link, Comment, Message, Subreddit]
    l_cls = [Listing, OrganicListing]

    classes  = [('%s: %s') % ('t'+ str(cl._type_id), cl.__name__ ) for cl in t_cls] \
             + [('%s: %s') % (cl.__name__, cl._js_cls) for cl in l_cls]

    res = ', '.join(classes)
    return unsafe('{ %s }' % res)

def calc_time_period(comment_time):
    # Set in front.py:GET_comments()
    previous_visits = c.previous_visits

    if not previous_visits:
        return ""

    rv = ""
    for i, visit in enumerate(previous_visits):
        if comment_time > visit:
            rv = "comment-period-%d" % i

    return rv

def comment_label(num_comments=None):
    if not num_comments:
        # generates "comment" the imperative verb
        com_label = _("comment {verb}")
        com_cls = 'comments empty may-blank'
    else:
        # generates "XX comments" as a noun
        com_label = ungettext("comment", "comments", num_comments)
        com_label = strings.number_label % dict(num=num_comments,
                                                thing=com_label)
        com_cls = 'comments may-blank'
    return com_label, com_cls

def replace_render(listing, item, render_func):
    def _replace_render(style = None, display = True):
        """
        A helper function for listings to set uncachable attributes on a
        rendered thing (item) to its proper display values for the current
        context.
        """
        style = style or c.render_style or 'html'
        replacements = {}

        if hasattr(item, 'child'):
            if item.child:
                replacements['childlisting'] = item.child.render(style=style)
            else:
                # Special case for when the comment tree wasn't built which
                # occurs both in the inbox and spam page view of comments.
                replacements['childlisting'] = None
        else:
            replacements['childlisting'] = ''

        #only LinkListing has a show_nums attribute
        if listing and hasattr(listing, "show_nums"):
            if listing.show_nums and item.num > 0:
                num = str(item.num)
            else:
                num = ""
            replacements["num"] = num

        if getattr(item, "rowstyle_cls", None):
            replacements["rowstyle"] = item.rowstyle_cls

        if hasattr(item, "num_comments"):
            com_label, com_cls = comment_label(item.num_comments)
            if style == "compact":
                com_label = unicode(item.num_comments)
            replacements['numcomments'] = com_label
            replacements['commentcls'] = com_cls

        if hasattr(item, "num_children"):
            label = ungettext("child", "children", item.num_children)
            numchildren_text = strings.number_label % {'num': item.num_children,
                                                       'thing': label}
            replacements['numchildren_text'] = numchildren_text

        replacements['display'] =  "" if display else "style='display:none'"

        if hasattr(item, "render_score"):
            # replace the score stub
            (replacements['scoredislikes'],
             replacements['scoreunvoted'],
             replacements['scorelikes'])  = item.render_score

        # compute the timesince here so we don't end up caching it
        if hasattr(item, "_date"):
            if hasattr(item, "promoted") and item.promoted is not None:
                from r2.lib import promote
                # promoted links are special in their date handling
                replacements['timesince'] = \
                    simplified_timesince(item._date - promote.timezone_offset)
            else:
                replacements['timesince'] = simplified_timesince(item._date)

            replacements['time_period'] = calc_time_period(item._date)

        # compute the last edited time here so we don't end up caching it
        if hasattr(item, "editted") and not isinstance(item.editted, bool):
            replacements['lastedited'] = simplified_timesince(item.editted)

        # Set in front.py:GET_comments()
        replacements['previous_visits_hex'] = c.previous_visits_hex

        renderer = render_func or item.render
        res = renderer(style = style, **replacements)

        if isinstance(res, (str, unicode)):
            rv = unsafe(res)
            if g.debug:
                for leftover in re.findall('<\$>(.+?)(?:<|$)', rv):
                    print "replace_render didn't replace %s" % leftover

            return rv

        return res

    return _replace_render

def get_domain(cname = False, subreddit = True, no_www = False):
    """
    returns the domain on the current subreddit, possibly including
    the subreddit part of the path, suitable for insertion after an
    "http://" and before a fullpath (i.e., something including the
    first '/') in a template.  The domain is updated to include the
    current port (request.port).  The effect of the arguments is:

     * no_www: if the domain ends up being g.domain, the default
       behavior is to prepend "www." to the front of it (for akamai).
       This flag will optionally disable it.

     * cname: whether to respect the value of c.cname and return
       c.site.domain rather than g.domain as the host name.

     * subreddit: if a cname is not used in the resulting path, flags
       whether or not to append to the domain the subreddit path (sans
       the trailing path).

    """
    # locally cache these lookups as this gets run in a loop in add_props
    domain = g.domain
    domain_prefix = c.domain_prefix
    site  = c.site
    ccname = c.cname
    if not no_www and domain_prefix:
        domain = domain_prefix + "." + domain
    if cname and ccname and site.domain:
        domain = site.domain
    if hasattr(request, "port") and request.port:
        domain += ":" + str(request.port)
    if (not ccname or not cname) and subreddit:
        domain += site.path.rstrip('/')
    return domain

def dockletStr(context, type, browser):
    domain      = get_domain()

    # while site_domain will hold the (possibly) cnamed version
    site_domain = get_domain(True)

    if type == "serendipity!":
        return "http://"+site_domain+"/random"
    elif type == "submit":
        return ("javascript:location.href='http://"+site_domain+
               "/submit?url='+encodeURIComponent(location.href)+'&title='+encodeURIComponent(document.title)")
    elif type == "reddit toolbar":
        return ("javascript:%20var%20h%20=%20window.location.href;%20h%20=%20'http://" +
                site_domain + "/s/'%20+%20escape(h);%20window.location%20=%20h;")
    else:
        # these are the linked/disliked buttons, which we have removed
        # from the UI
        return (("javascript:function b(){var u=encodeURIComponent(location.href);"
                 "var i=document.getElementById('redstat')||document.createElement('a');"
                 "var s=i.style;s.position='%(position)s';s.top='0';s.left='0';"
                 "s.zIndex='10002';i.id='redstat';"
                 "i.href='http://%(site_domain)s/submit?url='+u+'&title='+"
                 "encodeURIComponent(document.title);"
                 "var q=i.firstChild||document.createElement('img');"
                 "q.src='http://%(domain)s/d/%(type)s.png?v='+Math.random()+'&uh=%(modhash)s&u='+u;"
                 "i.appendChild(q);document.body.appendChild(i)};b()") %
                dict(position = "absolute" if browser == "ie" else "fixed",
                     domain = domain, site_domain = site_domain, type = type,
                     modhash = c.modhash if c.user else ''))



def add_sr(path, sr_path = True, nocname=False, force_hostname = False, retain_extension=True):
    """
    Given a path (which may be a full-fledged url or a relative path),
    parses the path and updates it to include the subreddit path
    according to the rules set by its arguments:

     * force_hostname: if True, force the url's hostname to be updated
       even if it is already set in the path, and subject to the
       c.cname/nocname combination.  If false, the path will still
       have its domain updated if no hostname is specified in the url.

     * nocname: when updating the hostname, overrides the value of
       c.cname to set the hostname to g.domain.  The default behavior
       is to set the hostname consistent with c.cname.

     * sr_path: if a cname is not used for the domain, updates the
       path to include c.site.path.

    For caching purposes: note that this function uses:
      c.cname, c.render_style, c.site.name
    """
    # don't do anything if it is just an anchor
    if path.startswith(('#', 'javascript:')):
        return path

    u = UrlParser(path)
    if sr_path and (nocname or not c.cname):
        u.path_add_subreddit(c.site)

    if not u.hostname or force_hostname:
        if c.secure:
            u.hostname = request.host
        else:
            u.hostname = get_domain(cname = (c.cname and not nocname),
                                    subreddit = False)

    if c.secure:
        u.scheme = "https"

    if retain_extension:
        if c.render_style == 'mobile':
            u.set_extension('mobile')

        elif c.render_style == 'compact':
            u.set_extension('compact')

    return u.unparse()

def join_urls(*urls):
    """joins a series of urls together without doubles slashes"""
    if not urls:
        return

    url = urls[0]
    for u in urls[1:]:
        if not url.endswith('/'):
            url += '/'
        while u.startswith('/'):
            u = utils.lstrips(u, '/')
        url += u
    return url

def style_line(button_width = None, bgcolor = "", bordercolor = ""):
    style_line = ''
    bordercolor = c.bordercolor or bordercolor
    bgcolor     = c.bgcolor or bgcolor
    if bgcolor:
        style_line += "background-color: #%s;" % bgcolor
    if bordercolor:
        style_line += "border: 1px solid #%s;" % bordercolor
    if button_width:
        style_line += "width: %spx;" % button_width
    return style_line

def choose_width(link, width):
    if width:
        return width - 5
    else:
        if hasattr(link, "_ups"):
            return 100 + (10 * (len(str(link._ups - link._downs))))
        else:
            return 110

# Appends to the list "attrs" a tuple of:
# <priority (higher trumps lower), letter,
#  css class, i18n'ed mouseover label, hyperlink (opt)>
def add_attr(attrs, kind, label=None, link=None, cssclass=None, symbol=None):
    from r2.lib.template_helpers import static

    symbol = symbol or kind

    if kind == 'F':
        priority = 1
        cssclass = 'friend'
        if not label:
            label = _('friend')
        if not link:
            link = '/prefs/friends'
    elif kind == 'S':
        priority = 2
        cssclass = 'submitter'
        if not label:
            label = _('submitter')
        if not link:
            raise ValueError ("Need a link")
    elif kind == 'M':
        priority = 3
        cssclass = 'moderator'
        if not label:
            raise ValueError ("Need a label")
        if not link:
            raise ValueError ("Need a link")
    elif kind == 'A':
        priority = 4
        cssclass = 'admin'
        if not label:
            label = _('reddit admin, speaking officially')
        if not link:
            link = '/about/team'
    elif kind in ('X', '@'):
        priority = 5
        cssclass = 'gray'
        if not label:
            raise ValueError ("Need a label")
    elif kind == 'V':
        priority = 6
        cssclass = 'green'
        if not label:
            raise ValueError ("Need a label")
    elif kind == 'B':
        priority = 7
        cssclass = 'wrong'
        if not label:
            raise ValueError ("Need a label")
    elif kind == 'special':
        priority = 98
    elif kind == "cake":
        priority = 99
        cssclass = "cakeday"
        symbol = "&#x1F370;"
        if not label:
            raise ValueError ("Need a label")
        if not link:
            raise ValueError ("Need a link")
    else:
        raise ValueError ("Got weird kind [%s]" % kind)

    attrs.append( (priority, symbol, cssclass, label, link) )


def search_url(query, subreddit, restrict_sr="off", sort=None, recent=None):
    import urllib
    query = _force_utf8(query)
    url_query = {"q": query}
    if restrict_sr:
        url_query["restrict_sr"] = restrict_sr
    if sort:
        url_query["sort"] = sort
    if recent:
        url_query["t"] = recent
    path = "/r/%s/search?" % subreddit if subreddit else "/search?"
    path += urllib.urlencode(url_query)
    return path


def format_number(number, locale=None):
    if not locale:
        locale = c.locale

    return babel.numbers.format_number(number, locale=locale)


def format_percent(ratio, locale=None):
    return babel.numbers.format_percent(ratio, locale=locale or c.locale)


def html_datetime(date):
    # Strip off the microsecond to appease the HTML5 gods, since
    # datetime.isoformat() returns too long of a microsecond value.
    # http://www.whatwg.org/specs/web-apps/current-work/multipage/common-microsyntaxes.html#times
    return date.replace(microsecond=0).isoformat()


def js_timestamp(date):
    return '%d' % (calendar.timegm(date.timetuple()) * 1000)


def simplified_timesince(date, include_tense=True):
    if date > timeago("1 minute"):
        return _("just now")

    since = []
    since.append(timesince(date))
    if include_tense:
        since.append(_("ago"))
    return " ".join(since)


def display_link_karma(karma):
    if not c.user_is_admin:
        return max(karma, g.link_karma_display_floor)
    return karma


def display_comment_karma(karma):
    if not c.user_is_admin:
        return max(karma, g.comment_karma_display_floor)
    return karma


def _ws(*args, **kwargs):
    """Helper function to get HTML escaped output from gettext"""
    return websafe(_(*args, **kwargs))
