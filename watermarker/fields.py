import StringIO
from django.db.models.fields.files import ImageFieldFile
import os
from PIL import Image
from django.core.files.base import File, ContentFile
from django.db.models import ImageField
import utils
from watermarker.models import Watermark

import logging

logger = logging.getLogger(__file__)

__author__ = 'matt'


class WatermarkImageField(ImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('blank', True)
        kwargs.setdefault('editable', False)
        kwargs.setdefault('max_length', 255)

        self.populate_from = kwargs.pop('populate_from', None)
        if self.populate_from is None:
            raise ValueError("missing 'populate_from' argument")

        self.watermark = kwargs.pop('watermark', None)
        if self.watermark is None:
            raise ValueError("missing 'watermark' argument")

        self.position = kwargs.pop('position', 'r')
        self.opacity = kwargs.pop('opacity', 0.5)
        self.tile = kwargs.pop('tile', False)
        self.scale = kwargs.pop('scale', 1.0)
        self.greyscale = kwargs.pop('greyscale', False)
        self.rotation = kwargs.pop('rotation', 0)
        self.quality = kwargs.pop('quality', 85)

        super(WatermarkImageField, self).__init__(*args, **kwargs)

    def create_watermark(self, model_instance):
        # get the watermark
        name = self.watermark
        try:
            watermark = Watermark.objects.get(name=name, is_active=True)
        except Watermark.DoesNotExist:
            logger.error('Watermark "%s" does not exist. Unable to watermark image %s' % (name, model_instance.pk))
            return

        # get the image to watermark
        image_field = getattr(model_instance, self.populate_from)
        target = Image.open(image_field.path)
        mark = Image.open(watermark.image.path)

        # determine the actual value that the parameters provided will render
        scale = utils.determine_scale(self.scale, target, mark)
        rotation = utils.determine_rotation(self.rotation, mark)
        pos = utils.determine_position(self.position, target, mark)

        params = {
            'position':  pos,
            'opacity':   self.opacity,
            'scale':     scale,
            'tile':      self.tile,
            'greyscale': self.greyscale,
            'rotation':  rotation,
        }
        logger.debug('Params: %s' % params)
        im = utils.watermark(target, mark, **params)

        image_io = StringIO.StringIO()
        image_io.name = os.path.basename(image_field.name)
        # check ext
        name, ext = os.path.splitext(image_io.name)
        if not ext or ext.lower() not in ('jpg', 'jpeg', 'png'):
            image_io.name = "%s%s" % (name, '.jpg')
        im.save(image_io, quality=self.quality)
        image_io.seek(0)
        return File(image_io)

    def pre_save(self, model_instance, add):
        file = super(WatermarkImageField, self).pre_save(model_instance, add)
        if not file or not os.path.exists(file.path):
            watermarked_file = self.create_watermark(model_instance)
            print "saving: %s" % watermarked_file.name
            file.save(watermarked_file.name, watermarked_file, save=False)
        return file

    def south_field_triple(self):
        """Returns a suitable description of this field for South."""
        # We'll just introspect the _actual_ field.
        from south.modelsinspector import introspector

        field_class = self.__class__.__module__ + "." + self.__class__.__name__
        args, kwargs = introspector(self)
        kwargs.update({
            'populate_from': repr(self.populate_from),
            'watermark': repr(self.watermark),
            'position': repr(self.position),
            'opacity': repr(self.opacity),
            'tile': repr(self.tile),
            'scale': repr(self.scale),
            'greyscale': repr(self.greyscale),
            'rotation': repr(self.rotation),
            'quality': repr(self.quality),
        })
        return field_class, args, kwargs
