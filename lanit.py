# coding=utf-8
import os

import ayah

from flask import Flask, render_template, flash, url_for, redirect, request
from flask.ext.redis import Redis

from utils import validate_url, generate_secret_key, strip_tags, get_current_timestamp, parse_date, seconds_to_datetime, datetime_to_seconds
from validation import is_valid_short_name, is_valid_secret_key

# Initialize Flask app
app = Flask(__name__)

# Load base configuration
app.config.from_pyfile('settings.py')

# Try configuration overriding with local settings file
app.config.from_pyfile('local_settings.py', silent=True)

# Setup logging for production
if not app.config['DEBUG']:
    import logging
    from logging.handlers import RotatingFileHandler

    file_handler = RotatingFileHandler(os.path.join(os.path.split(os.path.abspath(__file__))[0], 'log', 'flask.log'),
                                       maxBytes=1024 * 1024, backupCount=5, encoding="UTF-8")
    file_handler.setLevel(logging.WARNING)
    app.logger.addHandler(file_handler)

# Register template filters
app.jinja_env.filters['datetime_to_seconds'] = datetime_to_seconds
app.jinja_env.filters['seconds_to_datetime'] = seconds_to_datetime

# Setup Redis connection
redis = Redis()
redis.init_app(app)


@app.route('/', methods=['GET'])
def handle_list_events():
    """
    Display frontpage form
    """
    upcoming_events = get_upcoming_events()
    ongoing_events = get_ongoing_events()

    # Setup Are You A Human check
    ayah.configure(app.config['ARE_YOU_HUMAN_PUBLISHER_KEY'], app.config['ARE_YOU_HUMAN_SCORING_KEY'])
    ayah_html = ayah.get_publisher_html()

    return render_template('index.html', upcoming_events=upcoming_events, ongoing_events=ongoing_events,
                           ayah_html=ayah_html)


@app.route('/<short_name>', methods=['GET'])
def handle_event_redirect(short_name):
    """
    Get event URL and redirect user, flash and redirect to frontapge if not found
    """
    if not short_name:
        return redirect(url_for('handle_list_events'))

    redirect_url = get_event_url(short_name)

    if not redirect_url:
        flash(u'Pyytämääsi LANia ei löytynyt')
        redirect_url = '/'

    return redirect(redirect_url, 302)


@app.route('/add', methods=['GET', 'POST'])
def handle_add_event():
    """
    Validate and add event, flash and redirect to frontpage
    """

    # TODO Aikaperusteinen hidaste tapahtumien lisäyksen spämmäämiseen
    if request.method == 'GET':
        flash(u'Käytä lomaketta')
        return redirect(url_for('handle_list_events'))

    # Get data from form
    add_short_name = strip_tags(request.form['short_name'].strip())
    add_name = strip_tags(request.form['name'].strip())
    add_url = request.form['url'].strip().lower()
    add_start_time = strip_tags(request.form['start_time'].strip())
    add_end_time = strip_tags(request.form['end_time'].strip())
    ayah_session_secret = strip_tags(request.form['session_secret'].strip())

    # Setup Are You A Human check
    ayah.configure(app.config['ARE_YOU_HUMAN_PUBLISHER_KEY'], app.config['ARE_YOU_HUMAN_SCORING_KEY'])

    # Validate short name
    if is_valid_short_name(add_short_name) != True:
        flash(u'Tapahtuman lyhytnimi ei ole kelvollinen. Tarkista tiedot ja yritä uudelleen.')
        return redirect(url_for('handle_list_events'))

    # Parse times and validate them
    add_start_time = parse_date(add_start_time)
    add_end_time = parse_date(add_end_time)

    if add_start_time == False:
        flash(u'Tapahtuman alkuaika ei ole kelvollinen. Tarkista tiedot ja yritä uudelleen.')
        return redirect(url_for('handle_list_events'))

    if add_end_time == False:
        flash(u'Tapahtuman päättymisaika ei ole kelvollinen. Tarkista tiedot ja yritä uudelleen.')
        return redirect(url_for('handle_list_events'))

    # Check that end time is later than start time
    if add_start_time >= add_end_time:
        flash(u'Tapahtuma ei voi päättyä ennen alkamistaan. Tarkista tiedot ja yritä uudelleen.')
        return redirect(url_for('handle_list_events'))

    # Check if event already exists with short name
    if event_exists(add_short_name):
        flash(u'Tapahtuman lyhytnimi on jo käytössä. Valitse toinen nimi tai poista olemassa oleva tapahtuma.')
        return redirect(url_for('handle_list_events'))

    # Call Are You A Human scoring service
    if ayah.score_result(ayah_session_secret) == False:
        flash(u'Spämmitarkistus epäonnistui. Tarkista että et ole spämmirobotti ja/tai yritä uudelleen.')
        return redirect(url_for('handle_list_events'))

    # Request URL and check it's valid
    add_url = validate_url(add_url)
    if add_url == False:
        flash(u'Tapahtuman URL-osoite ei ole kelvollinen. Tarkista tiedot ja yritä uudelleen.')
        return redirect(url_for('handle_list_events'))

    # TODO Spämmitarkistuksia lyhyt nimi, nimi ja URL. Domain/sanalistan mukaan pisteytys.

    # Add event to system
    if add_event(short_name=add_short_name, name=add_name, url=add_url, start_time=add_start_time,
                 end_time=add_end_time) == False:
        flash(
            u'Tapahtuman lisäämisessä tapahtui mystinen virhe. Tarkista tiedot ja yritä uudelleen. Ongelman jatkuessa ota yhteyttä.')
        return redirect(url_for('handle_list_events'))
    else:
        secret_key = get_event_secret_key(add_short_name)
        flash(
            u'Tapahtuma lisättiin onnistuneesti. Tapahtuman salainen avain on %s. Pidä se tallessa esimerkiksi poistoa varten.' % secret_key)
        return redirect(url_for('handle_list_events'))


@app.route('/delete', methods=['GET', 'POST'])
def handle_remove_event():
    """
    Validate secret code and remove event, flash and redirect to frontpage
    """
    # TODO Aikaperusteinen hidaste avainten brute force -spämmäyksen estoon
    if request.method == 'GET':
        flash(u'Käytä lomaketta')
        return redirect(url_for('handle_list_events'))

    # Get data from form
    remove_short_name = request.form['short_name'].strip().lower()
    remove_secret = request.form['secret'].strip().lower()
    ayah_session_secret = strip_tags(request.form['session_secret'].strip())

    # Setup Are You A Human check
    ayah.configure(app.config['ARE_YOU_HUMAN_PUBLISHER_KEY'], app.config['ARE_YOU_HUMAN_SCORING_KEY'])

    # Validation
    if is_valid_short_name(remove_short_name) != True:
        flash(u'Lyhytnimi tai salainen avain ei täsmää. Tarkista tiedot ja yritä uudelleen.')
        return redirect(url_for('handle_list_events'))

    if is_valid_secret_key(remove_secret, app.config['SECRET_KEY_CHARACTERS']) != True:
        flash(u'Lyhytnimi tai salainen avain ei täsmää. Tarkista tiedot ja yritä uudelleen.')
        return redirect(url_for('handle_list_events'))

    if event_exists(remove_short_name) != True:
        flash(u'Lyhytnimi tai salainen avain ei täsmää. Tarkista tiedot ja yritä uudelleen.')
        return redirect(url_for('handle_list_events'))

    # Call Are You A Human scoring service
    if ayah.score_result(ayah_session_secret) == False:
        flash(u'Spämmitarkistus epäonnistui. Tarkista että et ole spämmirobotti ja/tai yritä uudelleen.')
        return redirect(url_for('handle_list_events'))

    if not remove_event_with_secret(remove_short_name, remove_secret):
        flash(u'Lyhytnimi tai salainen avain ei täsmää. Tarkista tiedot ja yritä uudelleen.')
        return redirect(url_for('handle_list_events'))
    else:
        flash(u'Tapahtuma poistettu onnistuneesti.')
        return redirect(url_for('handle_list_events'))


def get_upcoming_events():
    """
    Get events with start time in future sorted oldes first
    """
    redis_instance = app.extensions['redis']['REDIS']

    now_seconds = get_current_timestamp()

    upcoming_events = redis_instance.zrangebyscore(app.config['REDIS_KEY_EVENT_START'], now_seconds, '+inf')

    # Setup Redis transaction
    pipe = redis_instance.pipeline()

    # Add commands to transaction
    for short_name in upcoming_events:
        pipe.hgetall(app.config['REDIS_KEY_EVENT_INFO'] % short_name)

    # Execute and return True if no Falses in Redis multi bulk reply
    return pipe.execute()


def get_ongoing_events():
    """
    Get events with start time in past sorted oldest first.
    Expires and cleanup_events() should cause only relevant events to show up.
    """
    redis_instance = app.extensions['redis']['REDIS']

    now_seconds = get_current_timestamp()

    upcoming_events = redis_instance.zrangebyscore(app.config['REDIS_KEY_EVENT_START'], '-inf', now_seconds)

    # Setup Redis transaction
    pipe = redis_instance.pipeline()

    # Add commands to transaction
    for short_name in upcoming_events:
        pipe.hgetall(app.config['REDIS_KEY_EVENT_INFO'] % short_name)

    # Execute and return True if no Falses in Redis multi bulk reply
    return pipe.execute()


def add_event(short_name='', name='', secret_key='', url='', start_time=None, end_time=None):
    """
    Get event information and add it to Redis
    :param short_name: Id/short name
    :param name: Display name
    :param secret_key: Secret key for removing
    :param url: URL for redirection
    :param start_time: Python datetime object of event start time
    :param end_time: Python datetime object of event end time
    """

    # Generate new secret key if it's not provided
    if not secret_key:
        secret_key = generate_secret_key(allowed_characters=app.config['SECRET_KEY_CHARACTERS'])

    # Convert datetime objects to timestamp seconds
    start_seconds = datetime_to_seconds(start_time)
    end_seconds = datetime_to_seconds(end_time)

    # Setup dictionary of event information to save
    event_info = {
        'short_name': short_name,
        'name': name,
        'url': url,
        'secret_key': secret_key,
        'start_time': start_seconds,
        'end_time': end_seconds
    }

    redis_instance = app.extensions['redis']['REDIS']

    # Setup Redis transaction
    pipe = redis_instance.pipeline()

    # Add commands to transaction
    pipe.hmset(app.config['REDIS_KEY_EVENT_INFO'] % short_name, event_info)
    pipe.expireat(app.config['REDIS_KEY_EVENT_INFO'] % short_name, end_time)

    pipe.zadd(app.config['REDIS_KEY_EVENT_START'], short_name, start_seconds)
    pipe.zadd(app.config['REDIS_KEY_EVENT_END'], short_name, end_seconds)

    # Execute and return True if no Falses in Redis multi bulk reply
    return False not in pipe.execute()


def event_exists(short_name=''):
    """
    Check if event is already in system with short name
    """
    redis_instance = app.extensions['redis']['REDIS']
    return redis_instance.exists(app.config['REDIS_KEY_EVENT_INFO'] % short_name)


def remove_event(short_name=''):
    """
    Remove event from system with event short name
    """
    if not short_name:
        return False

    redis_instance = app.extensions['redis']['REDIS']

    # Setup Redis transaction
    pipe = redis_instance.pipeline()

    # Add commands to transaction
    pipe.delete(app.config['REDIS_KEY_EVENT_INFO'] % short_name)
    pipe.zrem(app.config['REDIS_KEY_EVENT_START'], short_name)
    pipe.zrem(app.config['REDIS_KEY_EVENT_END'], short_name)

    # Execute and return True if no Falses in Redis multi bulk reply
    return False not in pipe.execute()


def remove_event_with_secret(short_name='', secret_key=''):
    """
    Get event with short name and call removing if passed secret key matches found event key
    """
    if not short_name or not secret_key:
        return False

    redis_instance = app.extensions['redis']['REDIS']

    # Get secret key with event short name
    remove_secret_key = redis_instance.hget(app.config['REDIS_KEY_EVENT_INFO'] % short_name, 'secret_key')

    # Check if passed secret key matches
    if remove_secret_key == secret_key:
        # Match, call removing
        return remove_event(short_name=short_name)
    else:
        # No match or not found
        return False


def cleanup_events():
    """
    Cleanup old events from Redis. Redis key expires should take care of everything but sorted sets.
    """
    redis_instance = app.extensions['redis']['REDIS']

    # Get short names of old events
    now_seconds = get_current_timestamp()
    removable_names = redis_instance.zrangebyscore(app.config['REDIS_KEY_EVENT_END'], '-inf', now_seconds)

    # Setup Redis transaction
    pipe = redis_instance.pipeline()

    # Add commands to transaction
    pipe.zrem(app.config['REDIS_KEY_EVENT_START'], removable_names)
    pipe.zrem(app.config['REDIS_KEY_EVENT_END'], removable_names)

    # Execute and return True if no Falses in Redis multi bulk reply
    #return False not in pipe.execute()
    return pipe.execute()


def get_event_secret_key(short_name=''):
    """
    Get event secret key
    """
    if not short_name:
        return False

    redis_instance = app.extensions['redis']['REDIS']

    # Get secret key
    return redis_instance.hget(app.config['REDIS_KEY_EVENT_INFO'] % short_name, 'secret_key')


def get_event_url(short_name=''):
    """
    Get event secret key
    """
    if not short_name:
        return False

    redis_instance = app.extensions['redis']['REDIS']

    # Get secret key
    return redis_instance.hget(app.config['REDIS_KEY_EVENT_INFO'] % short_name, 'url')


@app.errorhandler(403)
def page_not_found(e):
    return render_template('403.html'), 403


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(410)
def page_not_found(e):
    return render_template('410.html'), 410


@app.errorhandler(500)
def page_not_found(e):
    return render_template('500.html'), 500


def _test():
    import doctest

    doctest.testmod()


if __name__ == '__main__':
    app.run()
