from neo_wrapper import SageMakerNeoWrapper, NeoParameters
from model_loader import ModelDefine
import cv2


def main():
    # create parameter
    model_define = ModelDefine.TF_SSD_MOBILE_NET_V2_COCO
    model_root_path = "model"
    target_device = "cpu"
    param = NeoParameters(model_define=model_define,
                          model_root_path=model_root_path,
                          target_device=target_device,
                          is_save_image_with_box=True)

    # create neo wrapper and initialize
    wrapper = SageMakerNeoWrapper(param)
    wrapper.load()

    # read image
    file_path = "data/dog.jpg"
    im = cv2.imread(file_path)  # shape is (H, W, C)
    cv2_images = [im]
    file_path_list = [file_path]

    # run inference
    size = (im.shape[1], im.shape[0])
    result = wrapper.run(original_images=cv2_images, output_size=size, file_name_list=file_path_list)
    print(result)


if __name__ == "__main__":
    main()
