#!/usr/bin/env python

from astropy import units as u
from astropy.time import Time

from google.cloud import datastore

from pocs.base import PanBase
from pocs.utils import current_time


class ObservatonsExporter(PanBase):
    """ A simple class for exporting observations to Google Datastore

    Observations are pulled from the corresponding mongo collection.
    """

    def __init__(self, date=None, project_id='panoptes-survey'):
        super(ObservatonsExporter, self).__init__()
        self.ds_client = datastore.Client(project_id)

        if date is None:
            date = (current_time() - 1. * u.day).datetime
        else:
            date = Time(date).datetime

        self.logger.debug("Export observations since {}", date)

        self.date = date

        self.units = dict()
        self.fields = dict()
        self.sequences = dict()
        self.images = dict()

        self.problems = list()

    def collect_entities(self):
        observations = self.db.observations.find(
            {'date': {'$gte': self.date}}
        )
        for obs_full in observations:
            try:
                self._build_observation_entity(obs_full['data'])
            except Exception as e:
                self.logger.warning(e)
                self.problems.append(obs_full)

    def _build_observation_entity(self, observation):
        obs = observation
        try:
            unit_id = obs['observer']
        except KeyError:
            unit_id = self.config['pan_id']

        if unit_id == 'Generic PANOPTES Unit':
            unit_id = self.config['pan_id']

        field_id = ''.join(x.capitalize() for x in obs['field_name'].replace('-', '').split(' '))
        if field_id.startswith('Alt_') or field_id.startswith('Az_'):
            return

        seq_id = obs['seq_time']
        img_id = obs['start_time']

        try:
            unit_key = self.units[unit_id].key
        except KeyError:
            unit_key = self.ds_client.key('Unit', unit_id)
            unit_entity = datastore.Entity(
                unit_key,
                exclude_from_indexes=['elevation']
            )
            unit_entity.update({
                'lat': obs['latitude'],
                'lon': obs['longitude'],
                'elevation': obs['elevation']
            })
            self.units[unit_id] = unit_entity

        try:
            field_key = self.fields[field_id].key
        except KeyError:
            field_key = self.ds_client.key('Field', field_id, parent=unit_key)
            field_entity = datastore.Entity(field_key)
            field_entity.update({
                'ra': obs['field_ra'],
                'dec': obs['field_dec'],
            })
            self.fields[field_id] = field_entity

        try:
            seq_key = self.sequences[seq_id].key
        except KeyError:
            seq_key = self.ds_client.key('Seq', seq_id, parent=field_key)
            seq_entity = datastore.Entity(
                seq_key,
                exclude_from_indexes=[
                    'set_size',
                    'merit',
                    'min_nexp',
                    'min_duration',
                    'priority',
                    'set_duration',
                    'ra_rate',
                ]
            )
            seq_entity.update({
                'set_size': obs['exp_set_size'],
                'exp_time': obs['exp_time'],
                'merit': obs['merit'],
                'min_nexp': obs['min_nexp'],
                'min_duration': obs['minimum_duration'],
                'priority': obs['priority'],
                'set_duration': obs['set_duration'],
                'ra_rate': obs['tracking_rate_ra'],
                'pocs_version': obs['creator']
            })
            self.sequences[seq_id] = seq_entity

        try:
            img_entity = self.images[img_id]
            # If here, we have the same image but different camera
            img_entity['cam_id'].append(obs['camera_uid'])
        except KeyError:
            if 'POINTING' in obs:
                if bool(obs['POINTING']) is True:
                    img_key = self.ds_client.key('Pointing', img_id, parent=seq_key)
                    obs['exp_time'] = 30.  # Handle bug where wasn't recorded correctly
            else:
                img_key = self.ds_client.key('Img', img_id, parent=seq_key)

            img_entity = datastore.Entity(
                img_key,
                exclude_from_indexes=[
                    'exp_num',
                ]
            )
            img_entity.update({
                'airmass': obs['airmass'],
                'exp_num': obs['current_exp'],
                'moon_frac': obs['moon_fraction'],
                'moon_sep': obs['moon_separation'],
                'ra_mnt': obs['ra_mnt'],
                'dec_mnt': obs['dec_mnt'],
                'ha_mnt': obs['ha_mnt'],
                'cam_id': [obs['camera_uid']]
            })
            self.images[img_id] = img_entity

    def send_to_datastore(self):
        # self.ds_client.put_multi(self.units.values())
        self.logger.debug("Sending {} field entities to datastore", len(self.fields))
        self.ds_client.put_multi(self.fields.values())

        self.logger.debug("Sending {} sequence entities to datastore", len(self.sequences))
        self.ds_client.put_multi(self.sequences.values())

        img_ents = list(self.images.values())
        while len(img_ents) > 0:
            images_batch = img_ents[0:500]
            self.logger.debug("Sending {}/{} images entities to datastore",
                              len(images_batch), len(self.images))
            self.ds_client.put_multi(images_batch)
            img_ents = img_ents[500:]


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(
        description="Export observations information to datastore")
    parser.add_argument('--date', default=None,
                        help='Export start date, e.g. 2016-01-01, defaults to yesterday')
    parser.add_argument('--auto-confirm', action='store_true', default=False,
                        help='Auto-confirm upload, implies verbose.')
    parser.add_argument('--verbose', action='store_true', default=False,
                        help='Verbose')

    args = parser.parse_args()

    if args.date is None:
        args.date = (current_time() - 1. * u.day).datetime
    else:
        args.date = Time(args.date).datetime

    if args.auto_confirm is False:
        args.verbose = True

    obs_exporter = ObservatonsExporter(date=args.date)
    obs_exporter.collect_entities()

    print("Found the following records:")
    print("\tFields: {}".format(len(obs_exporter.fields)))
    print("\tSeq:    {}".format(len(obs_exporter.sequences)))
    print("\tImgs:   {}".format(len(obs_exporter.images)))
    print("\tProblems:   {}".format(len(obs_exporter.problems)))

    if args.auto_confirm is not True:
        do_upload = input("Send to datastore? [Y/n]:")
        if do_upload.lower() == 'y' or do_upload == '':
            print("Starting upload")
            # obs_exporter.send_to_datastore()
        else:
            print("Skipping upload")
