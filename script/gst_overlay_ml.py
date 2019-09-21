import gi
import numpy as np
from coco import coco
from object_detection.utils import visualization_utils
from PIL import Image
from model_loader import TfModelZooLoader, ModelDefine
import dlr

gi.require_version('Gst', '1.0')
gi.require_version('GstBase', '1.0')
from gi.repository import Gst, GObject, GstBase


GST_OVERLAY_ML = 'gstoverlayml'
INPUT_SIZE = (640, 480)  # TODO : should set from outer


# https://lazka.github.io/pgi-docs/GstBase-1.0/classes/BaseTransform.html
class GstOverlayML(GstBase.BaseTransform):
    CHANNELS = 3  # RGB

    __gstmetadata__ = ("sample",
                       "Transform",
                       "sample",
                       "sample")

    __gsttemplates__ = (Gst.PadTemplate.new("src",
                                            Gst.PadDirection.SRC,
                                            Gst.PadPresence.ALWAYS,
                                            Gst.Caps.new_any()),
                        Gst.PadTemplate.new("sink",
                                            Gst.PadDirection.SINK,
                                            Gst.PadPresence.ALWAYS,
                                            Gst.Caps.new_any()))

    def __init__(self):
        super(GstOverlayML, self).__init__()

        # load model
        model_type = ModelDefine.TF_SSD_MOBILE_NET_V2_COCO
        model_root_path = "model"
        loader = TfModelZooLoader(model_root_path, model_type.value["url"])
        loader.setup()
        model_info = loader.get_model_detail()
        model_path = model_info.model_path_map["model_file"]

        # create DLR model
        self._model = dlr.DLRModel(model_path)

        # set input param
        self._input_tensor_name = model_type.value["input_tensor_name"]
        self._size = model_type.value["input_size"]

    def do_transform_ip(self, inbuffer):
        # convert inbuffer to ndarray
        # data format is HWC? (not contain N)
        np_buffer = ndarray_from_gst_buffer(inbuffer, INPUT_SIZE)

        # convert display size from (640, 480) to (300, 300)
        img = Image.fromarray(np_buffer)
        img_resized = img.resize(self._size)
        np_buffer_resized = np.asarray(img_resized)

        # get bounding box information
        # need to convert data format from CHW to NCHW
        input_tensor = np.array([np_buffer_resized])
        res = self._model.run({self._input_tensor_name: input_tensor})

        # recreate image to add bounding box
        recreate_image_with_bounding_boxes(np_buffer, res)

        # need to convert from np.array to GstBuffer
        outbytes = np_buffer.tobytes()
        outbuffer = Gst.Buffer.new_wrapped(outbytes)
        # TODO : need to add alpha channel to outbuffer(3channel -> 4channel)
        #inbuffer.remove_all_memory()
        #inbuffer = outbuffer
        return Gst.FlowReturn.OK


def recreate_image_with_bounding_boxes(image_array, res):
    boxes, classes, scores, num_det = res
    n_obj = int(num_det[0])
    target_boxes = []
    for j in range(n_obj):
        # check score
        cl_id = int(classes[0][j])
        label = coco.IMAGE_CLASSES[cl_id]
        score = scores[0][j]
        if score < 0.5:
            continue

        # check label (only person label is added)
        # TODO : label id should be got from coco.py
        if label != 1:
            continue

        # print each data
        box = boxes[0][j]
        print("  ", cl_id, label, score, box)
        target_boxes.append(box)

    # recreate image with bounding boxes if box is not empty
    if len(target_boxes) != 0:
        visualization_utils.draw_bounding_boxes_on_image_array(image_array, np.array(target_boxes))


def register(plugin):
    # https://lazka.github.io/pgi-docs/#GObject-2.0/functions.html#GObject.type_register
    type_to_register = GObject.type_register(GstOverlayML)

    # https://lazka.github.io/pgi-docs/#Gst-1.0/classes/Element.html#Gst.Element.register
    return Gst.Element.register(plugin, GST_OVERLAY_ML, 0, type_to_register)


def register_by_name(plugin_name):
    # Parameters explanation
    # https://lazka.github.io/pgi-docs/Gst-1.0/classes/Plugin.html#Gst.Plugin.register_static
    name = plugin_name
    description = "gst.Element draws on image buffer"
    version = '1.12.4'
    gst_license = 'LGPL'
    source_module = 'gstreamer'
    package = 'gstoverlay'
    origin = 'shotasakamoto554101@gmail.com'
    if not Gst.Plugin.register_static(Gst.VERSION_MAJOR, Gst.VERSION_MINOR,
                                      name, description,
                                      register, version, gst_license,
                                      source_module, package, origin):
        raise ImportError("Plugin {} not registered".format(plugin_name))
    return True


def get_buffer_size(caps):
    """
        Returns width, height of buffer from caps
        :param caps: https://lazka.github.io/pgi-docs/Gst-1.0/classes/Caps.html
        :type caps: Gst.Caps
        :rtype: bool, (int, int)
    """

    caps_struct = caps.get_structure(0)
    (success, width) = caps_struct.get_int('width')
    if not success:
        return False, (0, 0)
    (success, height) = caps_struct.get_int('height')
    if not success:
        return False, (0, 0)
    return True, (width, height)


def ndarray_from_gst_buffer(buf, input_size):
    size = buf.get_size()
    data = buf.extract_dup(0, size)
    img = np.ndarray((input_size[0], input_size[1], 4), buffer=data, dtype=np.uint8)
    img = img[:,:,0:3]
    return img


register_by_name(GST_OVERLAY_ML)
