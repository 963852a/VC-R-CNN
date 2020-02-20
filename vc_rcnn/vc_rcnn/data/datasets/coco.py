# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved.
import torch
import torchvision
import h5py
import numpy as np
from vc_rcnn.structures.bounding_box import BoxList
from vc_rcnn.structures.segmentation_mask import SegmentationMask
from vc_rcnn.structures.keypoint import PersonKeypoints


min_keypoints_per_image = 10


def _count_visible_keypoints(anno):
    return sum(sum(1 for v in ann["keypoints"][2::3] if v > 0) for ann in anno)


def _has_only_empty_bbox(anno):
    return all(any(o <= 1 for o in obj["bbox"][2:]) for obj in anno)


def has_valid_annotation(anno):
    # if it's empty, there is no annotation
    if len(anno) == 0:
        return False
    # if all boxes have close to zero area, there is no annotation
    if _has_only_empty_bbox(anno):
        return False
    # keypoints task have a slight different critera for considering
    # if an annotation is valid
    if "keypoints" not in anno[0]:
        return True
    # for keypoint detection tasks, only consider valid images those
    # containing at least min_keypoints_per_image
    if _count_visible_keypoints(anno) >= min_keypoints_per_image:
        return True
    return False


class COCODataset(torchvision.datasets.coco.CocoDetection):
    def __init__(
        self, ann_file, root, remove_images_without_annotations, bbox_file_path, num_threshold_object, transforms=None
    ):
        super(COCODataset, self).__init__(root, ann_file)
        # sort indices for reproducible results
        self.ids = sorted(self.ids)

        # filter images without detection annotations
        if remove_images_without_annotations:
            ids = []
            for img_id in self.ids:
                ann_ids = self.coco.getAnnIds(imgIds=img_id, iscrowd=None)
                anno = self.coco.loadAnns(ann_ids)
                if has_valid_annotation(anno) and len(anno) >= num_threshold_object:
                    ids.append(img_id)
            self.ids = ids

        self.categories = {cat['id']: cat['name'] for cat in self.coco.cats.values()}

        self.json_category_id_to_contiguous_id = {
            v: i + 1 for i, v in enumerate(self.coco.getCatIds())
        }
        self.contiguous_category_id_to_json_id = {
            v: k for k, v in self.json_category_id_to_contiguous_id.items()
        }
        self.id_to_img_map = {k: v for k, v in enumerate(self.ids)}
        self._transforms = transforms

        # bounding box file (numpy format), used for feature extraction during test
        self.box_dir = bbox_file_path

        self.is_train = remove_images_without_annotations

    def __getitem__(self, idx):
        img, anno = super(COCODataset, self).__getitem__(idx)
        anno = [obj for obj in anno if obj["iscrowd"] == 0]

        if self.is_train:
            assert len(anno) >= 3
            boxes = [obj["bbox"] for obj in anno]
            boxes = torch.as_tensor(boxes).reshape(-1, 4)  # guard against no boxes
            classes = [obj["category_id"] for obj in anno]
            classes = [self.json_category_id_to_contiguous_id[c] for c in classes]
            classes = torch.tensor(classes) - 1

            boxes = [obj["bbox"] for obj in anno]
            boxes = torch.as_tensor(boxes).reshape(-1, 4)  # guard against no boxes
            classes = [obj["category_id"] for obj in anno]
            classes = [self.json_category_id_to_contiguous_id[c] for c in classes]
            classes = torch.tensor(classes) - 1

            image_id = [obj['image_id'] for obj in anno]
            image_id = torch.tensor(image_id)
            sizes = [[w, h] for obj in anno]
            sizes = torch.tensor(sizes)

            target = BoxList(boxes, img.size, mode="xywh").convert("xyxy")

        # for feature extraction during testing (bottom up bbox here)
        else:
            image_id_bu = str(self.id_to_img_map[idx])
            boxes = np.load(self.box_dir + image_id_bu + '.npy')
            num_box = boxes.shape[0]
            boxes = torch.tensor(boxes)

            w, h = img.size[0], img.size[1]

            # #### for bottom_up data  ###########
            num_box = [num_box for i in range(boxes.size(0))]
            num_box = torch.tensor(num_box)
            sizes = [[w, h] for i in range(boxes.size(0))]
            sizes = torch.tensor(sizes)
            image_id = [int(image_id_bu) for i in range(boxes.size(0))]
            image_id = torch.tensor(image_id)
            classes = [0 for i in range(boxes.size(0))]
            classes = torch.tensor(classes)

            target = BoxList(boxes, img.size, mode="xyxy")

        # assert len(anno)>2
        # filter crowd annotations
        # TODO might be better to add an extra field


        # boxes = [obj["bbox"] for obj in anno]
        # boxes = torch.as_tensor(boxes).reshape(-1, 4)  # guard against no boxes
        # target = BoxList(boxes, img.size, mode="xywh").convert("xyxy")
        #
        # classes = [obj["category_id"] for obj in anno]
        # classes = [self.json_category_id_to_contiguous_id[c] for c in classes]
        # classes = torch.tensor(classes) - 1
        # target.add_field("labels", classes)

        # if anno and "segmentation" in anno[0]:
        #     masks = [obj["segmentation"] for obj in anno]
        #     masks = SegmentationMask(masks, img.size, mode='poly')
        #     target.add_field("masks", masks)
        #
        # if anno and "keypoints" in anno[0]:
        #     keypoints = [obj["keypoints"] for obj in anno]
        #     keypoints = PersonKeypoints(keypoints, img.size)
        #     target.add_field("keypoints", keypoints)

        # #### for bottom_up data  ###########
        #

        # ###############################


        w, h = img.size[0], img.size[1]



        ############ for coco_gt data ##########
        # boxes = [obj["bbox"] for obj in anno]
        # boxes = torch.as_tensor(boxes).reshape(-1, 4)  # guard against no boxes
        # classes = [obj["category_id"] for obj in anno]
        # classes = [self.json_category_id_to_contiguous_id[c] for c in classes]
        # classes = torch.tensor(classes) - 1

        # target.add_field("labels", classes)

        # # for test
        #
        # w, h = img.size[0], img.size[1]
        #
        # if str(anno[0]['image_id']) in self.bbox_10_100.keys():
        #     boxes = self.bbox_10_100[str(anno[0]['image_id'])]['bbox'][:]
        #     boxes = torch.tensor(boxes)
        #     classes = self.bbox_10_100[str(anno[0]['image_id'])]['class_label'][:]
        #     classes = torch.tensor(classes) - 1
        #
        #     image_id = [anno[0]['image_id'] for i in range(boxes.size(0))]
        #     image_id = torch.tensor(image_id)
        #     sizes = [[w, h] for i in range(boxes.size(0))]
        #     sizes = torch.tensor(sizes)
        #
        #
        # else:
        #     boxes = [obj["bbox"] for obj in anno]
        #     boxes = torch.as_tensor(boxes).reshape(-1, 4)  # guard against no boxes
        #     # target = BoxList(boxes, img.size, mode="xywh").convert("xyxy")
        #
        #     classes = [obj["category_id"] for obj in anno]
        #     classes = [self.json_category_id_to_contiguous_id[c] for c in classes]
        #     classes = torch.tensor(classes) - 1
        #

        ### for gt coco
        # image_id = [obj['image_id'] for obj in anno]
        # image_id = torch.tensor(image_id)
        # sizes = [[w, h] for obj in anno]
        # sizes = torch.tensor(sizes)
        #
        # target = BoxList(boxes, img.size, mode="xywh").convert("xyxy")

        # target = BoxList(boxes, img.size, mode="xyxy")

        target.add_field("labels", classes)
        target.add_field("image_id", image_id)
        target.add_field("orignal_size", sizes)
        target.add_field("num_box", num_box)


        target = target.clip_to_image(remove_empty=False)

        if self._transforms is not None:
            img, target = self._transforms(img, target)

        return img, target, idx

    def get_img_info(self, index):
        img_id = self.id_to_img_map[index]
        img_data = self.coco.imgs[img_id]
        return img_data
