import os

from warnings import warn

import psycopg2
from psycopg2.extras import DictCursor
from astropy.wcs import WCS


def get_db_proxy_conn(
        host='127.0.0.1',
        port=5432,
        db_name='panoptes',
        db_user='panoptes',
        db_pass=None,
        **kwargs):
    """Return postgres connection to local proxy.

    Note:
        The proxy must be started and authenticated to the appropriate instance
        before this function will work. See `$POCS/scripts/connect_clouddb_proxy.py`.

    Args:
        host (str, optional): Hostname, default localhost.
        port (str, optional): Port, default 5432.
        db_user (str, optional): Name of db user, default 'panoptes'.
        db_name (str, optional): Name of db, default 'postgres'.
        db_pass (str, optional): Password for given db and user, defaults to
            $PG_PASSWORD or None if not set.

    Returns:
        `psycopg2.Connection`: DB connection object.
    """
    if db_pass is None:
        db_pass = os.getenv('PGPASSWORD')

    conn_params = {
        'host': host,
        'port': port,
        'user': db_user,
        'dbname': db_name,
        'password': db_pass,
    }

    conn = psycopg2.connect(**conn_params)
    return conn


def get_cursor(**kwargs):
    """Get a Cursor object.

    Args:
        **kwargs: Passed to `get_db_prox_conn`

    Returns:
        `psycopg2.Cursor`: Cursor object.
    """
    conn = get_db_proxy_conn(**kwargs)
    cur = conn.cursor(cursor_factory=DictCursor)

    return cur


def meta_insert(table, conn=None, logger=None, **kwargs):
    """Inserts arbitrary key/value pairs into a table.

    Args:
        table (str): Table in which to insert.
        conn (None, optional): DB connection, if None then `get_db_proxy_conn`
            is used.
        logger (None, optional): A logger.
        **kwargs: List of key/value pairs corresponding to columns in the
            table.

    Returns:
        tuple|None: Returns the inserted row or None.
    """
    if conn is None:
        conn = get_db_proxy_conn()

    cur = conn.cursor()

    col_names = ','.join(kwargs.keys())
    col_val_holders = ','.join(['%s' for _ in range(len(kwargs))])

    insert_sql = 'INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING RETURNING *'.format(
        table, col_names, col_val_holders)

    try:
        cur.execute(insert_sql, list(kwargs.values()))
        conn.commit()
        return cur.fetchone()
    except Exception as e:
        conn.rollback()
        warn("Error on fetch: {}".format(e))
        if logger:
            logger.info("Can't insert row: {}".format(e))
        return None


def add_header_to_db(header, conn=None, logger=None):
    """Add FITS image info to metadb.

    Note:
        This function doesn't check header for proper entries and
        assumes a large list of keywords. See source for details.

    Args:
        header (dict): FITS Header data from an observation.
        conn (None, optional): DB connection, if None then `get_db_proxy_conn`
            is used.
        logger (None, optional): A logger.

    Returns:
        str: The image_id.
    """
    unit_id = int(header['OBSERVER'].strip().replace('PAN', ''))
    seq_id = header['SEQID'].strip()
    img_id = header['IMAGEID'].strip()
    camera_id = header['INSTRUME'].strip()

    unit_data = {
        'id': unit_id,
        'name': header['OBSERVER'].strip(),
        'lat': float(header['LAT-OBS']),
        'lon': float(header['LONG-OBS']),
        'elevation': float(header['ELEV-OBS']),
    }
    meta_insert('units', conn=conn, logger=logger, **unit_data)

    camera_data = {
        'unit_id': unit_id,
        'id': camera_id,
    }
    meta_insert('cameras', conn=conn, logger=logger, **camera_data)

    seq_data = {
        'id': seq_id,
        'unit_id': unit_id,
        'start_date': header['SEQID'].split('_')[-1],
        'exp_time': header['EXPTIME'],
        'ra_rate': header['RA-RATE'],
        'pocs_version': header['CREATOR'],
        'piaa_state': header.get('PSTATE', 'initial'),
    }

    try:
        wcs = WCS(header)
        if wcs.is_celestial:
            bl, tl, tr, br = WCS(header).calc_footprint()  # Corners
            seq_data['coord_bounds'] = '(({}, {}), ({}, {}))'.format(
                bl[0], bl[1],
                tr[0], tr[1]
            )
        else:
            seq_data['piaa_state'] = 'unsolved'

        if logger:
            logger.info("Inserting sequence: {}".format(seq_data))

        meta_insert('sequences', conn=conn, logger=logger, **seq_data)

        if logger:
            logger.info("Sequence inserted: {}".format(seq_id))
    except Exception as e:
        if logger:
            logger.info("Can't get bounds: {}".format(e))
        if 'coord_bounds' in seq_data:
            del seq_data['coord_bounds']
        try:
            meta_insert('sequences', conn=conn, logger=logger, **seq_data)
        except Exception as e:
            if logger:
                logger.info("Can't insert sequence: {}".format(seq_id))
            raise e

    image_data = {
        'id': img_id,
        'sequence_id': seq_id,
        'date_obs': header['DATE-OBS'],
        'moon_fraction': header['MOONFRAC'],
        'moon_separation': header['MOONSEP'],
        'ra_mnt': header['RA-MNT'],
        'ha_mnt': header['HA-MNT'],
        'dec_mnt': header['DEC-MNT'],
        'airmass': header['AIRMASS'],
        'exp_time': header['EXPTIME'],
        'iso': header['ISO'],
        'camera_id': camera_id,
        'cam_temp': header['CAMTEMP'].split(' ')[0],
        'cam_colortmp': header['COLORTMP'],
        'cam_circconf': header['CIRCCONF'].split(' ')[0],
        'cam_measrggb': header['MEASRGGB'],
        'cam_red_balance': header['REDBAL'],
        'cam_blue_balance': header['BLUEBAL'],
        'file_path': header.get('FILEPATH', None)
    }

    # Add plate-solved info.
    try:
        image_data['center_ra'] = header['CRVAL1']
        image_data['center_dec'] = header['CRVAL2']
    except KeyError:
        pass

    img_row = meta_insert('images', conn=conn, logger=logger, **image_data)

    return img_row
