from collections import OrderedDict

use_image = True

# Ordering: http://unicode.org/emoji/charts/emoji-ordering.txt

emoticons = OrderedDict([
    ('Smileys', [
        # group: Smileys
        ('u263a.png', None),  # Category image

        # subgroup: face-positive
        ('u1f600.png', [u'\U0001f600', ':>']),
        ('u1f601.png', [u'\U0001f601']),
        ('u1f602.png', [u'\U0001f602', ':\'-)', ':\')']),
        ('u1f923.png', [u'\U0001f923']),
        ('u1f603.png', [u'\U0001f603', ':-D', ':D', '=D']),
        ('u1f604.png', [u'\U0001f604']),
        ('u1f605.png', [u'\U0001f605']),
        ('u1f606.png', [u'\U0001f606']),
        ('u1f609.png', [u'\U0001f609', ';-)', ';)']),
        ('u1f60a.png', [u'\U0001f60a']),
        ('u1f60b.png', [u'\U0001f60b']),
        ('u1f60e.png', [u'\U0001f60e', '8-)', 'B-)']),
        ('u1f60d.png', [u'\U0001f60d', '<3']),
        ('u1f618.png', [u'\U0001f618', ':-{}', ':-*', ':*']),
        ('u1f617.png', [u'\U0001f617']),
        ('u1f619.png', [u'\U0001f619']),
        ('u1f61a.png', [u'\U0001f61a']),
        ('u263a.png', [u'\u263a', ':-)', ':)', '=)', '=]', ':]']),
        ('u1f642.png', [u'\U0001f642']),
        ('u1f917.png', [u'\U0001f917']),

        # subgroup: face-neutral
        ('u1f914.png', [u'\U0001f914']),
        ('u1f610.png', [u'\U0001f610', ':-|', ':|']),
        ('u1f611.png', [u'\U0001f611']),
        ('u1f636.png', [u'\U0001f636']),
        ('u1f644.png', [u'\U0001f644']),
        ('u1f60f.png', [u'\U0001f60f']),
        ('u1f623.png', [u'\U0001f623']),
        ('u1f625.png', [u'\U0001f625']),
        ('u1f62e.png', [u'\U0001f62e', '=-O', ':-O', ':O']),
        ('u1f910.png', [u'\U0001f910']),
        ('u1f62f.png', [u'\U0001f62f', ':o']),
        ('u1f62a.png', [u'\U0001f62a']),
        ('u1f62b.png', [u'\U0001f62b']),
        ('u1f634.png', [u'\U0001f634']),
        ('u1f60c.png', [u'\U0001f60c']),
        ('u1f61b.png', [u'\U0001f61b', ':-P', ':P', ':-þ', ':þ']),
        ('u1f61c.png', [u'\U0001f61c']),
        ('u1f61d.png', [u'\U0001f61d']),
        ('u1f924.png', [u'\U0001f924']),
        ('u1f612.png', [u'\U0001f612']),
        ('u1f613.png', [u'\U0001f613']),
        ('u1f614.png', [u'\U0001f614']),
        ('u1f615.png', [u'\U0001f615']),
        ('u1f643.png', [u'\U0001f643']),
        ('u1f911.png', [u'\U0001f911']),
        ('u1f632.png', [u'\U0001f632']),

        # subgroup: face-negative
        ('u2639.png', [u'\u2639', ':-/', ':/', ':-\\', ':\\', ':-S', ':S', ':-[', ':[']),
        ('u1f641.png', [u'\U0001f641']),
        ('u1f616.png', [u'\U0001f616']),
        ('u1f61e.png', [u'\U0001f61e', ':-(', ':(']),
        ('u1f61f.png', [u'\U0001f61f']),
        ('u1f624.png', [u'\U0001f624']),
        ('u1f622.png', [u'\U0001f622', ':\'-(', ':\'(', ';-(', ';(', ';\'-(']),
        ('u1f62d.png', [u'\U0001f62d']),
        ('u1f626.png', [u'\U0001f626']),
        ('u1f627.png', [u'\U0001f627']),
        ('u1f628.png', [u'\U0001f628']),
        ('u1f629.png', [u'\U0001f629']),
        ('u1f62c.png', [u'\U0001f62c']),
        ('u1f630.png', [u'\U0001f630']),
        ('u1f631.png', [u'\U0001f631']),
        ('u1f633.png', [u'\U0001f633', ':-$', ':$']),
        ('u1f635.png', [u'\U0001f635']),
        ('u1f621.png', [u'\U0001f621']),
        ('u1f620.png', [u'\U0001f620', ':-@', ':@']),

        # subgroup: face-sick
        ('u1f637.png', [u'\U0001f637']),
        ('u1f912.png', [u'\U0001f912']),
        ('u1f915.png', [u'\U0001f915']),
        ('u1f922.png', [u'\U0001f922']),
        ('u1f927.png', [u'\U0001f927']),


        # subgroup: face-role
        ('u1f607.png', [u'\U0001f607']),
        ('u1f920.png', [u'\U0001f920']),
        ('u1f921.png', [u'\U0001f921']),
        ('u1f925.png', [u'\U0001f925']),
        ('u1f913.png', [u'\U0001f913']),

        # subgroup: face-fantasy
        ('u1f608.png', [u'\U0001f608', ']:->', '>:-)', '>:)']),
        ('u1f47f.png', [u'\U0001f47f']),
        ('u1f479.png', [u'\U0001f479']),
        ('u1f47a.png', [u'\U0001f47a']),
        ('u1f480.png', [u'\U0001f480']),
        ('u2620.png', [u'\u2620']),
        ('u1f47b.png', [u'\U0001f47b']),
        ('u1f47d.png', [u'\U0001f47d']),
        ('u1f47e.png', [u'\U0001f47e']),
        ('u1f916.png', [u'\U0001f916']),
        ('u1f4a9.png', [u'\U0001f4a9']),

        # subgroup: cat-face
        ('u1f63a.png', [u'\U0001f63a']),
        ('u1f638.png', [u'\U0001f638']),
        ('u1f639.png', [u'\U0001f639']),
        ('u1f63b.png', [u'\U0001f63b']),
        ('u1f63c.png', [u'\U0001f63c']),
        ('u1f63d.png', [u'\U0001f63d']),
        ('u1f640.png', [u'\U0001f640']),
        ('u1f63f.png', [u'\U0001f63f']),
        ('u1f63e.png', [u'\U0001f63e']),

        # subgroup: monkey-face
        ('u1f648.png', [u'\U0001f648']),
        ('u1f649.png', [u'\U0001f649']),
        ('u1f64a.png', [u'\U0001f64a']),

        ]),

    ('People', [
        # group: People
        ('u1f575.png', None),  # Category image

        # subgroup: person
        (None, [
            ('u1f476.png', [u'\U0001f476']),
            ('u1f476_1f3fb.png', [u'\U0001f476\U0001f3fb']),
            ('u1f476_1f3fc.png', [u'\U0001f476\U0001f3fc']),
            ('u1f476_1f3fd.png', [u'\U0001f476\U0001f3fd']),
            ('u1f476_1f3fe.png', [u'\U0001f476\U0001f3fe']),
            ('u1f476_1f3ff.png', [u'\U0001f476\U0001f3ff']),
            ]),

        (None, [
            ('u1f466.png', [u'\U0001f466']),
            ('u1f466_1f3fb.png', [u'\U0001f466\U0001f3fb']),
            ('u1f466_1f3fc.png', [u'\U0001f466\U0001f3fc']),
            ('u1f466_1f3fd.png', [u'\U0001f466\U0001f3fd']),
            ('u1f466_1f3fe.png', [u'\U0001f466\U0001f3fe']),
            ('u1f466_1f3ff.png', [u'\U0001f466\U0001f3ff']),
            ]),

        (None, [
            ('u1f467.png', [u'\U0001f467']),
            ('u1f467_1f3fb.png', [u'\U0001f467\U0001f3fb']),
            ('u1f467_1f3fc.png', [u'\U0001f467\U0001f3fc']),
            ('u1f467_1f3fd.png', [u'\U0001f467\U0001f3fd']),
            ('u1f467_1f3fe.png', [u'\U0001f467\U0001f3fe']),
            ('u1f467_1f3ff.png', [u'\U0001f467\U0001f3ff']),
            ]),

        (None, [
            ('u1f468.png', [u'\U0001f468']),
            ('u1f468_1f3fb.png', [u'\U0001f468\U0001f3fb']),
            ('u1f468_1f3fc.png', [u'\U0001f468\U0001f3fc']),
            ('u1f468_1f3fd.png', [u'\U0001f468\U0001f3fd']),
            ('u1f468_1f3fe.png', [u'\U0001f468\U0001f3fe']),
            ('u1f468_1f3ff.png', [u'\U0001f468\U0001f3ff']),
            ]),

        (None, [
            ('u1f469.png', [u'\U0001f469']),
            ('u1f469_1f3fb.png', [u'\U0001f469\U0001f3fb']),
            ('u1f469_1f3fc.png', [u'\U0001f469\U0001f3fc']),
            ('u1f469_1f3fd.png', [u'\U0001f469\U0001f3fd']),
            ('u1f469_1f3fe.png', [u'\U0001f469\U0001f3fe']),
            ('u1f469_1f3ff.png', [u'\U0001f469\U0001f3ff']),
            ]),

        (None, [
            ('u1f474.png', [u'\U0001f474']),
            ('u1f474_1f3fb.png', [u'\U0001f474\U0001f3fb']),
            ('u1f474_1f3fc.png', [u'\U0001f474\U0001f3fc']),
            ('u1f474_1f3fd.png', [u'\U0001f474\U0001f3fd']),
            ('u1f474_1f3fe.png', [u'\U0001f474\U0001f3fe']),
            ('u1f474_1f3ff.png', [u'\U0001f474\U0001f3ff']),
            ]),

        (None, [
            ('u1f475.png', [u'\U0001f475']),
            ('u1f475_1f3fb.png', [u'\U0001f475\U0001f3fb']),
            ('u1f475_1f3fc.png', [u'\U0001f475\U0001f3fc']),
            ('u1f475_1f3fd.png', [u'\U0001f475\U0001f3fd']),
            ('u1f475_1f3fe.png', [u'\U0001f475\U0001f3fe']),
            ('u1f475_1f3ff.png', [u'\U0001f475\U0001f3ff']),
            ]),

        # subgroup: person-role
        (None, [
            ('u1f468_200d_2695.png', [u'\U0001f468\u200d\u2695']),
            ('u1f468_1f3fb_200d_2695.png', [u'\U0001f468\U0001f3fb\u200d\u2695']),
            ('u1f468_1f3fc_200d_2695.png', [u'\U0001f468\U0001f3fc\u200d\u2695']),
            ('u1f468_1f3fd_200d_2695.png', [u'\U0001f468\U0001f3fd\u200d\u2695']),
            ('u1f468_1f3fe_200d_2695.png', [u'\U0001f468\U0001f3fe\u200d\u2695']),
            ('u1f468_1f3ff_200d_2695.png', [u'\U0001f468\U0001f3ff\u200d\u2695']),
            ]),

        (None, [
            ('u1f469_200d_2695.png', [u'\U0001f469\u200d\u2695']),
            ('u1f469_1f3fb_200d_2695.png', [u'\U0001f469\U0001f3fb\u200d\u2695']),
            ('u1f469_1f3fc_200d_2695.png', [u'\U0001f469\U0001f3fc\u200d\u2695']),
            ('u1f469_1f3fd_200d_2695.png', [u'\U0001f469\U0001f3fd\u200d\u2695']),
            ('u1f469_1f3fe_200d_2695.png', [u'\U0001f469\U0001f3fe\u200d\u2695']),
            ('u1f469_1f3ff_200d_2695.png', [u'\U0001f469\U0001f3ff\u200d\u2695']),
            ]),

        (None, [
            ('u1f468_200d_1f393.png', [u'\U0001f468\u200d\U0001f393']),
            ('u1f468_1f3fb_200d_1f393.png', [u'\U0001f468\U0001f3fb\u200d\U0001f393']),
            ('u1f468_1f3fc_200d_1f393.png', [u'\U0001f468\U0001f3fc\u200d\U0001f393']),
            ('u1f468_1f3fd_200d_1f393.png', [u'\U0001f468\U0001f3fd\u200d\U0001f393']),
            ('u1f468_1f3fe_200d_1f393.png', [u'\U0001f468\U0001f3fe\u200d\U0001f393']),
            ('u1f468_1f3ff_200d_1f393.png', [u'\U0001f468\U0001f3ff\u200d\U0001f393']),
            ]),

        (None, [
            ('u1f469_200d_1f393.png', [u'\U0001f469\u200d\U0001f393']),
            ('u1f469_1f3fb_200d_1f393.png', [u'\U0001f469\U0001f3fb\u200d\U0001f393']),
            ('u1f469_1f3fc_200d_1f393.png', [u'\U0001f469\U0001f3fc\u200d\U0001f393']),
            ('u1f469_1f3fd_200d_1f393.png', [u'\U0001f469\U0001f3fd\u200d\U0001f393']),
            ('u1f469_1f3fe_200d_1f393.png', [u'\U0001f469\U0001f3fe\u200d\U0001f393']),
            ('u1f469_1f3ff_200d_1f393.png', [u'\U0001f469\U0001f3ff\u200d\U0001f393']),
            ]),

        (None, [
            ('u1f468_200d_1f3eb.png', [u'\U0001f468\u200d\U0001f3eb']),
            ('u1f468_1f3fb_200d_1f3eb.png', [u'\U0001f468\U0001f3fb\u200d\U0001f3eb']),
            ('u1f468_1f3fc_200d_1f3eb.png', [u'\U0001f468\U0001f3fc\u200d\U0001f3eb']),
            ('u1f468_1f3fd_200d_1f3eb.png', [u'\U0001f468\U0001f3fd\u200d\U0001f3eb']),
            ('u1f468_1f3fe_200d_1f3eb.png', [u'\U0001f468\U0001f3fe\u200d\U0001f3eb']),
            ('u1f468_1f3ff_200d_1f3eb.png', [u'\U0001f468\U0001f3ff\u200d\U0001f3eb']),
            ]),

        (None, [
            ('u1f469_200d_1f3eb.png', [u'\U0001f469\u200d\U0001f3eb']),
            ('u1f469_1f3fb_200d_1f3eb.png', [u'\U0001f469\U0001f3fb\u200d\U0001f3eb']),
            ('u1f469_1f3fc_200d_1f3eb.png', [u'\U0001f469\U0001f3fc\u200d\U0001f3eb']),
            ('u1f469_1f3fd_200d_1f3eb.png', [u'\U0001f469\U0001f3fd\u200d\U0001f3eb']),
            ('u1f469_1f3fe_200d_1f3eb.png', [u'\U0001f469\U0001f3fe\u200d\U0001f3eb']),
            ('u1f469_1f3ff_200d_1f3eb.png', [u'\U0001f469\U0001f3ff\u200d\U0001f3eb']),
            ]),

        (None, [
            ('u1f468_200d_2696.png', [u'\U0001f468\u200d\u2696']),
            ('u1f468_1f3fb_200d_2696.png', [u'\U0001f468\U0001f3fb\u200d\u2696']),
            ('u1f468_1f3fc_200d_2696.png', [u'\U0001f468\U0001f3fc\u200d\u2696']),
            ('u1f468_1f3fd_200d_2696.png', [u'\U0001f468\U0001f3fd\u200d\u2696']),
            ('u1f468_1f3fe_200d_2696.png', [u'\U0001f468\U0001f3fe\u200d\u2696']),
            ('u1f468_1f3ff_200d_2696.png', [u'\U0001f468\U0001f3ff\u200d\u2696']),
            ]),

        (None, [
            ('u1f469_200d_2696.png', [u'\U0001f469\u200d\u2696']),
            ('u1f469_1f3fb_200d_2696.png', [u'\U0001f469\U0001f3fb\u200d\u2696']),
            ('u1f469_1f3fc_200d_2696.png', [u'\U0001f469\U0001f3fc\u200d\u2696']),
            ('u1f469_1f3fd_200d_2696.png', [u'\U0001f469\U0001f3fd\u200d\u2696']),
            ('u1f469_1f3fe_200d_2696.png', [u'\U0001f469\U0001f3fe\u200d\u2696']),
            ('u1f469_1f3ff_200d_2696.png', [u'\U0001f469\U0001f3ff\u200d\u2696']),
            ]),

        (None, [
            ('u1f468_200d_1f33e.png', [u'\U0001f468\u200d\U0001f33e']),
            ('u1f468_1f3fb_200d_1f33e.png', [u'\U0001f468\U0001f3fb\u200d\U0001f33e']),
            ('u1f468_1f3fc_200d_1f33e.png', [u'\U0001f468\U0001f3fc\u200d\U0001f33e']),
            ('u1f468_1f3fd_200d_1f33e.png', [u'\U0001f468\U0001f3fd\u200d\U0001f33e']),
            ('u1f468_1f3fe_200d_1f33e.png', [u'\U0001f468\U0001f3fe\u200d\U0001f33e']),
            ('u1f468_1f3ff_200d_1f33e.png', [u'\U0001f468\U0001f3ff\u200d\U0001f33e']),
            ]),

        (None, [
            ('u1f469_200d_1f33e.png', [u'\U0001f469\u200d\U0001f33e']),
            ('u1f469_1f3fb_200d_1f33e.png', [u'\U0001f469\U0001f3fb\u200d\U0001f33e']),
            ('u1f469_1f3fc_200d_1f33e.png', [u'\U0001f469\U0001f3fc\u200d\U0001f33e']),
            ('u1f469_1f3fd_200d_1f33e.png', [u'\U0001f469\U0001f3fd\u200d\U0001f33e']),
            ('u1f469_1f3fe_200d_1f33e.png', [u'\U0001f469\U0001f3fe\u200d\U0001f33e']),
            ('u1f469_1f3ff_200d_1f33e.png', [u'\U0001f469\U0001f3ff\u200d\U0001f33e']),
            ]),

        (None, [
            ('u1f468_200d_1f373.png', [u'\U0001f468\u200d\U0001f373']),
            ('u1f468_1f3fb_200d_1f373.png', [u'\U0001f468\U0001f3fb\u200d\U0001f373']),
            ('u1f468_1f3fc_200d_1f373.png', [u'\U0001f468\U0001f3fc\u200d\U0001f373']),
            ('u1f468_1f3fd_200d_1f373.png', [u'\U0001f468\U0001f3fd\u200d\U0001f373']),
            ('u1f468_1f3fe_200d_1f373.png', [u'\U0001f468\U0001f3fe\u200d\U0001f373']),
            ('u1f468_1f3ff_200d_1f373.png', [u'\U0001f468\U0001f3ff\u200d\U0001f373']),
            ]),

        (None, [
            ('u1f469_200d_1f373.png', [u'\U0001f469\u200d\U0001f373']),
            ('u1f469_1f3fb_200d_1f373.png', [u'\U0001f469\U0001f3fb\u200d\U0001f373']),
            ('u1f469_1f3fc_200d_1f373.png', [u'\U0001f469\U0001f3fc\u200d\U0001f373']),
            ('u1f469_1f3fd_200d_1f373.png', [u'\U0001f469\U0001f3fd\u200d\U0001f373']),
            ('u1f469_1f3fe_200d_1f373.png', [u'\U0001f469\U0001f3fe\u200d\U0001f373']),
            ('u1f469_1f3ff_200d_1f373.png', [u'\U0001f469\U0001f3ff\u200d\U0001f373']),
            ]),

        (None, [
            ('u1f468_200d_1f527.png', [u'\U0001f468\u200d\U0001f527']),
            ('u1f468_1f3fb_200d_1f527.png', [u'\U0001f468\U0001f3fb\u200d\U0001f527']),
            ('u1f468_1f3fc_200d_1f527.png', [u'\U0001f468\U0001f3fc\u200d\U0001f527']),
            ('u1f468_1f3fd_200d_1f527.png', [u'\U0001f468\U0001f3fd\u200d\U0001f527']),
            ('u1f468_1f3fe_200d_1f527.png', [u'\U0001f468\U0001f3fe\u200d\U0001f527']),
            ('u1f468_1f3ff_200d_1f527.png', [u'\U0001f468\U0001f3ff\u200d\U0001f527']),
            ]),

        (None, [
            ('u1f469_200d_1f527.png', [u'\U0001f469\u200d\U0001f527']),
            ('u1f469_1f3fb_200d_1f527.png', [u'\U0001f469\U0001f3fb\u200d\U0001f527']),
            ('u1f469_1f3fc_200d_1f527.png', [u'\U0001f469\U0001f3fc\u200d\U0001f527']),
            ('u1f469_1f3fd_200d_1f527.png', [u'\U0001f469\U0001f3fd\u200d\U0001f527']),
            ('u1f469_1f3fe_200d_1f527.png', [u'\U0001f469\U0001f3fe\u200d\U0001f527']),
            ('u1f469_1f3ff_200d_1f527.png', [u'\U0001f469\U0001f3ff\u200d\U0001f527']),
            ]),

        (None, [
            ('u1f468_200d_1f3ed.png', [u'\U0001f468\u200d\U0001f3ed']),
            ('u1f468_1f3fb_200d_1f3ed.png', [u'\U0001f468\U0001f3fb\u200d\U0001f3ed']),
            ('u1f468_1f3fc_200d_1f3ed.png', [u'\U0001f468\U0001f3fc\u200d\U0001f3ed']),
            ('u1f468_1f3fd_200d_1f3ed.png', [u'\U0001f468\U0001f3fd\u200d\U0001f3ed']),
            ('u1f468_1f3fe_200d_1f3ed.png', [u'\U0001f468\U0001f3fe\u200d\U0001f3ed']),
            ('u1f468_1f3ff_200d_1f3ed.png', [u'\U0001f468\U0001f3ff\u200d\U0001f3ed']),
            ]),

        (None, [
            ('u1f469_200d_1f3ed.png', [u'\U0001f469\u200d\U0001f3ed']),
            ('u1f469_1f3fb_200d_1f3ed.png', [u'\U0001f469\U0001f3fb\u200d\U0001f3ed']),
            ('u1f469_1f3fc_200d_1f3ed.png', [u'\U0001f469\U0001f3fc\u200d\U0001f3ed']),
            ('u1f469_1f3fd_200d_1f3ed.png', [u'\U0001f469\U0001f3fd\u200d\U0001f3ed']),
            ('u1f469_1f3fe_200d_1f3ed.png', [u'\U0001f469\U0001f3fe\u200d\U0001f3ed']),
            ('u1f469_1f3ff_200d_1f3ed.png', [u'\U0001f469\U0001f3ff\u200d\U0001f3ed']),
            ]),


        (None, [
            ('u1f468_200d_1f4bc.png', [u'\U0001f468\u200d\U0001f4bc']),
            ('u1f468_1f3fb_200d_1f4bc.png', [u'\U0001f468\U0001f3fb\u200d\U0001f4bc']),
            ('u1f468_1f3fc_200d_1f4bc.png', [u'\U0001f468\U0001f3fc\u200d\U0001f4bc']),
            ('u1f468_1f3fd_200d_1f4bc.png', [u'\U0001f468\U0001f3fd\u200d\U0001f4bc']),
            ('u1f468_1f3fe_200d_1f4bc.png', [u'\U0001f468\U0001f3fe\u200d\U0001f4bc']),
            ('u1f468_1f3ff_200d_1f4bc.png', [u'\U0001f468\U0001f3ff\u200d\U0001f4bc']),
            ]),

        (None, [
            ('u1f469_200d_1f4bc.png', [u'\U0001f469\u200d\U0001f4bc']),
            ('u1f469_1f3fb_200d_1f4bc.png', [u'\U0001f469\U0001f3fb\u200d\U0001f4bc']),
            ('u1f469_1f3fc_200d_1f4bc.png', [u'\U0001f469\U0001f3fc\u200d\U0001f4bc']),
            ('u1f469_1f3fd_200d_1f4bc.png', [u'\U0001f469\U0001f3fd\u200d\U0001f4bc']),
            ('u1f469_1f3fe_200d_1f4bc.png', [u'\U0001f469\U0001f3fe\u200d\U0001f4bc']),
            ('u1f469_1f3ff_200d_1f4bc.png', [u'\U0001f469\U0001f3ff\u200d\U0001f4bc']),
            ]),

        (None, [
            ('u1f468_200d_1f52c.png', [u'\U0001f468\u200d\U0001f52c']),
            ('u1f468_1f3fb_200d_1f52c.png', [u'\U0001f468\U0001f3fb\u200d\U0001f52c']),
            ('u1f468_1f3fc_200d_1f52c.png', [u'\U0001f468\U0001f3fc\u200d\U0001f52c']),
            ('u1f468_1f3fd_200d_1f52c.png', [u'\U0001f468\U0001f3fd\u200d\U0001f52c']),
            ('u1f468_1f3fe_200d_1f52c.png', [u'\U0001f468\U0001f3fe\u200d\U0001f52c']),
            ('u1f468_1f3ff_200d_1f52c.png', [u'\U0001f468\U0001f3ff\u200d\U0001f52c']),
            ]),

        (None, [
            ('u1f469_200d_1f52c.png', [u'\U0001f469\u200d\U0001f52c']),
            ('u1f469_1f3fb_200d_1f52c.png', [u'\U0001f469\U0001f3fb\u200d\U0001f52c']),
            ('u1f469_1f3fc_200d_1f52c.png', [u'\U0001f469\U0001f3fc\u200d\U0001f52c']),
            ('u1f469_1f3fd_200d_1f52c.png', [u'\U0001f469\U0001f3fd\u200d\U0001f52c']),
            ('u1f469_1f3fe_200d_1f52c.png', [u'\U0001f469\U0001f3fe\u200d\U0001f52c']),
            ('u1f469_1f3ff_200d_1f52c.png', [u'\U0001f469\U0001f3ff\u200d\U0001f52c']),
            ]),

        (None, [
            ('u1f468_200d_1f4bb.png', [u'\U0001f468\u200d\U0001f4bb']),
            ('u1f468_1f3fb_200d_1f4bb.png', [u'\U0001f468\U0001f3fb\u200d\U0001f4bb']),
            ('u1f468_1f3fc_200d_1f4bb.png', [u'\U0001f468\U0001f3fc\u200d\U0001f4bb']),
            ('u1f468_1f3fd_200d_1f4bb.png', [u'\U0001f468\U0001f3fd\u200d\U0001f4bb']),
            ('u1f468_1f3fe_200d_1f4bb.png', [u'\U0001f468\U0001f3fe\u200d\U0001f4bb']),
            ('u1f468_1f3ff_200d_1f4bb.png', [u'\U0001f468\U0001f3ff\u200d\U0001f4bb']),
            ]),

        (None, [
            ('u1f469_200d_1f4bb.png', [u'\U0001f469\u200d\U0001f4bb']),
            ('u1f469_1f3fb_200d_1f4bb.png', [u'\U0001f469\U0001f3fb\u200d\U0001f4bb']),
            ('u1f469_1f3fc_200d_1f4bb.png', [u'\U0001f469\U0001f3fc\u200d\U0001f4bb']),
            ('u1f469_1f3fd_200d_1f4bb.png', [u'\U0001f469\U0001f3fd\u200d\U0001f4bb']),
            ('u1f469_1f3fe_200d_1f4bb.png', [u'\U0001f469\U0001f3fe\u200d\U0001f4bb']),
            ('u1f469_1f3ff_200d_1f4bb.png', [u'\U0001f469\U0001f3ff\u200d\U0001f4bb']),
            ]),

        (None, [
            ('u1f468_200d_1f3a4.png', [u'\U0001f468\u200d\U0001f3a4']),
            ('u1f468_1f3fb_200d_1f3a4.png', [u'\U0001f468\U0001f3fb\u200d\U0001f3a4']),
            ('u1f468_1f3fc_200d_1f3a4.png', [u'\U0001f468\U0001f3fc\u200d\U0001f3a4']),
            ('u1f468_1f3fd_200d_1f3a4.png', [u'\U0001f468\U0001f3fd\u200d\U0001f3a4']),
            ('u1f468_1f3fe_200d_1f3a4.png', [u'\U0001f468\U0001f3fe\u200d\U0001f3a4']),
            ('u1f468_1f3ff_200d_1f3a4.png', [u'\U0001f468\U0001f3ff\u200d\U0001f3a4']),
            ]),

        (None, [
            ('u1f469_200d_1f3a4.png', [u'\U0001f469\u200d\U0001f3a4']),
            ('u1f469_1f3fb_200d_1f3a4.png', [u'\U0001f469\U0001f3fb\u200d\U0001f3a4']),
            ('u1f469_1f3fc_200d_1f3a4.png', [u'\U0001f469\U0001f3fc\u200d\U0001f3a4']),
            ('u1f469_1f3fd_200d_1f3a4.png', [u'\U0001f469\U0001f3fd\u200d\U0001f3a4']),
            ('u1f469_1f3fe_200d_1f3a4.png', [u'\U0001f469\U0001f3fe\u200d\U0001f3a4']),
            ('u1f469_1f3ff_200d_1f3a4.png', [u'\U0001f469\U0001f3ff\u200d\U0001f3a4']),
            ]),

        (None, [
            ('u1f468_200d_1f3a8.png', [u'\U0001f468\u200d\U0001f3a8']),
            ('u1f468_1f3fb_200d_1f3a8.png', [u'\U0001f468\U0001f3fb\u200d\U0001f3a8']),
            ('u1f468_1f3fc_200d_1f3a8.png', [u'\U0001f468\U0001f3fc\u200d\U0001f3a8']),
            ('u1f468_1f3fd_200d_1f3a8.png', [u'\U0001f468\U0001f3fd\u200d\U0001f3a8']),
            ('u1f468_1f3fe_200d_1f3a8.png', [u'\U0001f468\U0001f3fe\u200d\U0001f3a8']),
            ('u1f468_1f3ff_200d_1f3a8.png', [u'\U0001f468\U0001f3ff\u200d\U0001f3a8']),
            ]),

        (None, [
            ('u1f469_200d_1f3a8.png', [u'\U0001f469\u200d\U0001f3a8']),
            ('u1f469_1f3fb_200d_1f3a8.png', [u'\U0001f469\U0001f3fb\u200d\U0001f3a8']),
            ('u1f469_1f3fc_200d_1f3a8.png', [u'\U0001f469\U0001f3fc\u200d\U0001f3a8']),
            ('u1f469_1f3fd_200d_1f3a8.png', [u'\U0001f469\U0001f3fd\u200d\U0001f3a8']),
            ('u1f469_1f3fe_200d_1f3a8.png', [u'\U0001f469\U0001f3fe\u200d\U0001f3a8']),
            ('u1f469_1f3ff_200d_1f3a8.png', [u'\U0001f469\U0001f3ff\u200d\U0001f3a8']),
            ]),

        (None, [
            ('u1f468_200d_2708.png', [u'\U0001f468\u200d\u2708']),
            ('u1f468_1f3fb_200d_2708.png', [u'\U0001f468\U0001f3fb\u200d\u2708']),
            ('u1f468_1f3fc_200d_2708.png', [u'\U0001f468\U0001f3fc\u200d\u2708']),
            ('u1f468_1f3fd_200d_2708.png', [u'\U0001f468\U0001f3fd\u200d\u2708']),
            ('u1f468_1f3fe_200d_2708.png', [u'\U0001f468\U0001f3fe\u200d\u2708']),
            ('u1f468_1f3ff_200d_2708.png', [u'\U0001f468\U0001f3ff\u200d\u2708']),
            ]),

        (None, [
            ('u1f469_200d_2708.png', [u'\U0001f469\u200d\u2708']),
            ('u1f469_1f3fb_200d_2708.png', [u'\U0001f469\U0001f3fb\u200d\u2708']),
            ('u1f469_1f3fc_200d_2708.png', [u'\U0001f469\U0001f3fc\u200d\u2708']),
            ('u1f469_1f3fd_200d_2708.png', [u'\U0001f469\U0001f3fd\u200d\u2708']),
            ('u1f469_1f3fe_200d_2708.png', [u'\U0001f469\U0001f3fe\u200d\u2708']),
            ('u1f469_1f3ff_200d_2708.png', [u'\U0001f469\U0001f3ff\u200d\u2708']),
            ]),

        (None, [
            ('u1f468_200d_1f680.png', [u'\U0001f468\u200d\U0001f680']),
            ('u1f468_1f3fb_200d_1f680.png', [u'\U0001f468\U0001f3fb\u200d\U0001f680']),
            ('u1f468_1f3fc_200d_1f680.png', [u'\U0001f468\U0001f3fc\u200d\U0001f680']),
            ('u1f468_1f3fd_200d_1f680.png', [u'\U0001f468\U0001f3fd\u200d\U0001f680']),
            ('u1f468_1f3fe_200d_1f680.png', [u'\U0001f468\U0001f3fe\u200d\U0001f680']),
            ('u1f468_1f3ff_200d_1f680.png', [u'\U0001f468\U0001f3ff\u200d\U0001f680']),
            ]),

        (None, [
            ('u1f469_200d_1f680.png', [u'\U0001f469\u200d\U0001f680']),
            ('u1f469_1f3fb_200d_1f680.png', [u'\U0001f469\U0001f3fb\u200d\U0001f680']),
            ('u1f469_1f3fc_200d_1f680.png', [u'\U0001f469\U0001f3fc\u200d\U0001f680']),
            ('u1f469_1f3fd_200d_1f680.png', [u'\U0001f469\U0001f3fd\u200d\U0001f680']),
            ('u1f469_1f3fe_200d_1f680.png', [u'\U0001f469\U0001f3fe\u200d\U0001f680']),
            ('u1f469_1f3ff_200d_1f680.png', [u'\U0001f469\U0001f3ff\u200d\U0001f680']),
            ]),

        (None, [
            ('u1f468_200d_1f692.png', [u'\U0001f468\u200d\U0001f692']),
            ('u1f468_1f3fb_200d_1f692.png', [u'\U0001f468\U0001f3fb\u200d\U0001f692']),
            ('u1f468_1f3fc_200d_1f692.png', [u'\U0001f468\U0001f3fc\u200d\U0001f692']),
            ('u1f468_1f3fd_200d_1f692.png', [u'\U0001f468\U0001f3fd\u200d\U0001f692']),
            ('u1f468_1f3fe_200d_1f692.png', [u'\U0001f468\U0001f3fe\u200d\U0001f692']),
            ('u1f468_1f3ff_200d_1f692.png', [u'\U0001f468\U0001f3ff\u200d\U0001f692']),
            ]),

        (None, [
            ('u1f469_200d_1f692.png', [u'\U0001f469\u200d\U0001f692']),
            ('u1f469_1f3fb_200d_1f692.png', [u'\U0001f469\U0001f3fb\u200d\U0001f692']),
            ('u1f469_1f3fc_200d_1f692.png', [u'\U0001f469\U0001f3fc\u200d\U0001f692']),
            ('u1f469_1f3fd_200d_1f692.png', [u'\U0001f469\U0001f3fd\u200d\U0001f692']),
            ('u1f469_1f3fe_200d_1f692.png', [u'\U0001f469\U0001f3fe\u200d\U0001f692']),
            ('u1f469_1f3ff_200d_1f692.png', [u'\U0001f469\U0001f3ff\u200d\U0001f692']),
            ]),

        (None, [
            ('u1f46e_200d_2640.png', [u'\U0001f46e\u200d\u2640']),
            ('u1f46e_1f3fb_200d_2640.png', [u'\U0001f46e\U0001f3fb\u200d\u2640']),
            ('u1f46e_1f3fc_200d_2640.png', [u'\U0001f46e\U0001f3fc\u200d\u2640']),
            ('u1f46e_1f3fd_200d_2640.png', [u'\U0001f46e\U0001f3fd\u200d\u2640']),
            ('u1f46e_1f3fe_200d_2640.png', [u'\U0001f46e\U0001f3fe\u200d\u2640']),
            ('u1f46e_1f3ff_200d_2640.png', [u'\U0001f46e\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f46e_200d_2642.png', [u'\U0001f46e\u200d\u2642', u'\U0001f46e']),
            ('u1f46e_1f3fb_200d_2642.png', [u'\U0001f46e\U0001f3fb\u200d\u2642', u'\U0001f46e\U0001f3fb']),
            ('u1f46e_1f3fc_200d_2642.png', [u'\U0001f46e\U0001f3fc\u200d\u2642', u'\U0001f46e\U0001f3fc']),
            ('u1f46e_1f3fd_200d_2642.png', [u'\U0001f46e\U0001f3fd\u200d\u2642', u'\U0001f46e\U0001f3fd']),
            ('u1f46e_1f3fe_200d_2642.png', [u'\U0001f46e\U0001f3fe\u200d\u2642', u'\U0001f46e\U0001f3fe']),
            ('u1f46e_1f3ff_200d_2642.png', [u'\U0001f46e\U0001f3ff\u200d\u2642', u'\U0001f46e\U0001f3ff']),
            ]),

        (None, [
            ('u1f575_200d_2640.png', [u'\U0001f575\u200d\u2640']),
            ('u1f575_1f3fb_200d_2640.png', [u'\U0001f575\U0001f3fb\u200d\u2640']),
            ('u1f575_1f3fc_200d_2640.png', [u'\U0001f575\U0001f3fc\u200d\u2640']),
            ('u1f575_1f3fd_200d_2640.png', [u'\U0001f575\U0001f3fd\u200d\u2640']),
            ('u1f575_1f3fe_200d_2640.png', [u'\U0001f575\U0001f3fe\u200d\u2640']),
            ('u1f575_1f3ff_200d_2640.png', [u'\U0001f575\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f575_200d_2642.png', [u'\U0001f575\u200d\u2642', u'\U0001f575']),
            ('u1f575_1f3fb_200d_2642.png', [u'\U0001f575\U0001f3fb\u200d\u2642', u'\U0001f575\U0001f3fb']),
            ('u1f575_1f3fc_200d_2642.png', [u'\U0001f575\U0001f3fc\u200d\u2642', u'\U0001f575\U0001f3fc']),
            ('u1f575_1f3fd_200d_2642.png', [u'\U0001f575\U0001f3fd\u200d\u2642', u'\U0001f575\U0001f3fd']),
            ('u1f575_1f3fe_200d_2642.png', [u'\U0001f575\U0001f3fe\u200d\u2642', u'\U0001f575\U0001f3fe']),
            ('u1f575_1f3ff_200d_2642.png', [u'\U0001f575\U0001f3ff\u200d\u2642', u'\U0001f575\U0001f3ff']),
            ]),

        (None, [
            ('u1f482_200d_2640.png', [u'\U0001f482\u200d\u2640']),
            ('u1f482_1f3fb_200d_2640.png', [u'\U0001f482\U0001f3fb\u200d\u2640']),
            ('u1f482_1f3fc_200d_2640.png', [u'\U0001f482\U0001f3fc\u200d\u2640']),
            ('u1f482_1f3fd_200d_2640.png', [u'\U0001f482\U0001f3fd\u200d\u2640']),
            ('u1f482_1f3fe_200d_2640.png', [u'\U0001f482\U0001f3fe\u200d\u2640']),
            ('u1f482_1f3ff_200d_2640.png', [u'\U0001f482\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f482_200d_2642.png', [u'\U0001f482\u200d\u2642', u'\U0001f482']),
            ('u1f482_1f3fb_200d_2642.png', [u'\U0001f482\U0001f3fb\u200d\u2642', u'\U0001f482\U0001f3fb']),
            ('u1f482_1f3fc_200d_2642.png', [u'\U0001f482\U0001f3fc\u200d\u2642', u'\U0001f482\U0001f3fc']),
            ('u1f482_1f3fd_200d_2642.png', [u'\U0001f482\U0001f3fd\u200d\u2642', u'\U0001f482\U0001f3fd']),
            ('u1f482_1f3fe_200d_2642.png', [u'\U0001f482\U0001f3fe\u200d\u2642', u'\U0001f482\U0001f3fe']),
            ('u1f482_1f3ff_200d_2642.png', [u'\U0001f482\U0001f3ff\u200d\u2642', u'\U0001f482\U0001f3ff']),
            ]),

        (None, [
            ('u1f477_200d_2640.png', [u'\U0001f477\u200d\u2640']),
            ('u1f477_1f3fb_200d_2640.png', [u'\U0001f477\U0001f3fb\u200d\u2640']),
            ('u1f477_1f3fc_200d_2640.png', [u'\U0001f477\U0001f3fc\u200d\u2640']),
            ('u1f477_1f3fd_200d_2640.png', [u'\U0001f477\U0001f3fd\u200d\u2640']),
            ('u1f477_1f3fe_200d_2640.png', [u'\U0001f477\U0001f3fe\u200d\u2640']),
            ('u1f477_1f3ff_200d_2640.png', [u'\U0001f477\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f477_200d_2642.png', [u'\U0001f477\u200d\u2642', u'\U0001f477']),
            ('u1f477_1f3fb_200d_2642.png', [u'\U0001f477\U0001f3fb\u200d\u2642', u'\U0001f477\U0001f3fb']),
            ('u1f477_1f3fc_200d_2642.png', [u'\U0001f477\U0001f3fc\u200d\u2642', u'\U0001f477\U0001f3fc']),
            ('u1f477_1f3fd_200d_2642.png', [u'\U0001f477\U0001f3fd\u200d\u2642', u'\U0001f477\U0001f3fd']),
            ('u1f477_1f3fe_200d_2642.png', [u'\U0001f477\U0001f3fe\u200d\u2642', u'\U0001f477\U0001f3fe']),
            ('u1f477_1f3ff_200d_2642.png', [u'\U0001f477\U0001f3ff\u200d\u2642', u'\U0001f477\U0001f3ff']),
            ]),

        (None, [
            ('u1f934.png', [u'\U0001f934']),
            ('u1f934_1f3fb.png', [u'\U0001f934\U0001f3fb']),
            ('u1f934_1f3fc.png', [u'\U0001f934\U0001f3fc']),
            ('u1f934_1f3fd.png', [u'\U0001f934\U0001f3fd']),
            ('u1f934_1f3fe.png', [u'\U0001f934\U0001f3fe']),
            ('u1f934_1f3ff.png', [u'\U0001f934\U0001f3ff']),
            ]),

        (None, [
            ('u1f478.png', [u'\U0001f478']),
            ('u1f478_1f3fb.png', [u'\U0001f478\U0001f3fb']),
            ('u1f478_1f3fc.png', [u'\U0001f478\U0001f3fc']),
            ('u1f478_1f3fd.png', [u'\U0001f478\U0001f3fd']),
            ('u1f478_1f3fe.png', [u'\U0001f478\U0001f3fe']),
            ('u1f478_1f3ff.png', [u'\U0001f478\U0001f3ff']),
            ]),

        (None, [
            ('u1f473_200d_2640.png', [u'\U0001f473\u200d\u2640']),
            ('u1f473_1f3fb_200d_2640.png', [u'\U0001f473\U0001f3fb\u200d\u2640']),
            ('u1f473_1f3fc_200d_2640.png', [u'\U0001f473\U0001f3fc\u200d\u2640']),
            ('u1f473_1f3fd_200d_2640.png', [u'\U0001f473\U0001f3fd\u200d\u2640']),
            ('u1f473_1f3fe_200d_2640.png', [u'\U0001f473\U0001f3fe\u200d\u2640']),
            ('u1f473_1f3ff_200d_2640.png', [u'\U0001f473\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f473_200d_2642.png', [u'\U0001f473\u200d\u2642', u'\U0001f473']),
            ('u1f473_1f3fb_200d_2642.png', [u'\U0001f473\U0001f3fb\u200d\u2642', u'\U0001f473\U0001f3fb']),
            ('u1f473_1f3fc_200d_2642.png', [u'\U0001f473\U0001f3fc\u200d\u2642', u'\U0001f473\U0001f3fc']),
            ('u1f473_1f3fd_200d_2642.png', [u'\U0001f473\U0001f3fd\u200d\u2642', u'\U0001f473\U0001f3fd']),
            ('u1f473_1f3fe_200d_2642.png', [u'\U0001f473\U0001f3fe\u200d\u2642', u'\U0001f473\U0001f3fe']),
            ('u1f473_1f3ff_200d_2642.png', [u'\U0001f473\U0001f3ff\u200d\u2642', u'\U0001f473\U0001f3ff']),
            ]),

        (None, [
            ('u1f472.png', [u'\U0001f472']),
            ('u1f472_1f3fb.png', [u'\U0001f472\U0001f3fb']),
            ('u1f472_1f3fc.png', [u'\U0001f472\U0001f3fc']),
            ('u1f472_1f3fd.png', [u'\U0001f472\U0001f3fd']),
            ('u1f472_1f3fe.png', [u'\U0001f472\U0001f3fe']),
            ('u1f472_1f3ff.png', [u'\U0001f472\U0001f3ff']),
            ]),

        (None, [
            ('u1f471_200d_2640.png', [u'\U0001f471\u200d\u2640']),
            ('u1f471_1f3fb_200d_2640.png', [u'\U0001f471\U0001f3fb\u200d\u2640']),
            ('u1f471_1f3fc_200d_2640.png', [u'\U0001f471\U0001f3fc\u200d\u2640']),
            ('u1f471_1f3fd_200d_2640.png', [u'\U0001f471\U0001f3fd\u200d\u2640']),
            ('u1f471_1f3fe_200d_2640.png', [u'\U0001f471\U0001f3fe\u200d\u2640']),
            ('u1f471_1f3ff_200d_2640.png', [u'\U0001f471\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f471_200d_2642.png', [u'\U0001f471\u200d\u2642', u'\U0001f471']),
            ('u1f471_1f3fb_200d_2642.png', [u'\U0001f471\U0001f3fb\u200d\u2642', u'\U0001f471\U0001f3fb']),
            ('u1f471_1f3fc_200d_2642.png', [u'\U0001f471\U0001f3fc\u200d\u2642', u'\U0001f471\U0001f3fb']),
            ('u1f471_1f3fd_200d_2642.png', [u'\U0001f471\U0001f3fd\u200d\u2642', u'\U0001f471\U0001f3fb']),
            ('u1f471_1f3fe_200d_2642.png', [u'\U0001f471\U0001f3fe\u200d\u2642', u'\U0001f471\U0001f3fb']),
            ('u1f471_1f3ff_200d_2642.png', [u'\U0001f471\U0001f3ff\u200d\u2642', u'\U0001f471\U0001f3fb']),
            ]),

        (None, [
            ('u1f935.png', [u'\U0001f935']),
            ('u1f935_1f3fb.png', [u'\U0001f935\U0001f3fb']),
            ('u1f935_1f3fc.png', [u'\U0001f935\U0001f3fc']),
            ('u1f935_1f3fd.png', [u'\U0001f935\U0001f3fd']),
            ('u1f935_1f3fe.png', [u'\U0001f935\U0001f3fe']),
            ('u1f935_1f3ff.png', [u'\U0001f935\U0001f3ff']),
            ]),

        (None, [
            ('u1f470.png', [u'\U0001f470']),
            ('u1f470_1f3fb.png', [u'\U0001f470\U0001f3fb']),
            ('u1f470_1f3fc.png', [u'\U0001f470\U0001f3fc']),
            ('u1f470_1f3fd.png', [u'\U0001f470\U0001f3fd']),
            ('u1f470_1f3fe.png', [u'\U0001f470\U0001f3fe']),
            ('u1f470_1f3ff.png', [u'\U0001f470\U0001f3ff']),
            ]),

        (None, [
            ('u1f930.png', [u'\U0001f930']),
            ('u1f930_1f3fb.png', [u'\U0001f930\U0001f3fb']),
            ('u1f930_1f3fc.png', [u'\U0001f930\U0001f3fc']),
            ('u1f930_1f3fd.png', [u'\U0001f930\U0001f3fd']),
            ('u1f930_1f3fe.png', [u'\U0001f930\U0001f3fe']),
            ('u1f930_1f3ff.png', [u'\U0001f930\U0001f3ff']),
            ]),

        # subgroup: person-fantasy
        (None, [
            ('u1f47c.png', [u'\U0001f47c']),
            ('u1f47c_1f3fb.png', [u'\U0001f47c\U0001f3fb']),
            ('u1f47c_1f3fc.png', [u'\U0001f47c\U0001f3fc']),
            ('u1f47c_1f3fd.png', [u'\U0001f47c\U0001f3fd']),
            ('u1f47c_1f3fe.png', [u'\U0001f47c\U0001f3fe']),
            ('u1f47c_1f3ff.png', [u'\U0001f47c\U0001f3ff']),
            ]),

        (None, [
            ('u1f385.png', [u'\U0001f385']),
            ('u1f385_1f3fb.png', [u'\U0001f385\U0001f3fb']),
            ('u1f385_1f3fc.png', [u'\U0001f385\U0001f3fc']),
            ('u1f385_1f3fd.png', [u'\U0001f385\U0001f3fd']),
            ('u1f385_1f3fe.png', [u'\U0001f385\U0001f3fe']),
            ('u1f385_1f3ff.png', [u'\U0001f385\U0001f3ff']),
            ]),

        (None, [
            ('u1f936.png', [u'\U0001f936']),
            ('u1f936_1f3fb.png', [u'\U0001f936\U0001f3fb']),
            ('u1f936_1f3fc.png', [u'\U0001f936\U0001f3fc']),
            ('u1f936_1f3fd.png', [u'\U0001f936\U0001f3fd']),
            ('u1f936_1f3fe.png', [u'\U0001f936\U0001f3fe']),
            ('u1f936_1f3ff.png', [u'\U0001f936\U0001f3ff']),
            ]),

        # subgroup: person-gesture
        (None, [
            ('u1f64d_200d_2640.png', [u'\U0001f64d\u200d\u2640', u'\U0001f64d']),
            ('u1f64d_1f3fb_200d_2640.png', [u'\U0001f64d\U0001f3fb\u200d\u2640', u'\U0001f64d\U0001f3fb']),
            ('u1f64d_1f3fc_200d_2640.png', [u'\U0001f64d\U0001f3fc\u200d\u2640', u'\U0001f64d\U0001f3fc']),
            ('u1f64d_1f3fd_200d_2640.png', [u'\U0001f64d\U0001f3fd\u200d\u2640', u'\U0001f64d\U0001f3fd']),
            ('u1f64d_1f3fe_200d_2640.png', [u'\U0001f64d\U0001f3fe\u200d\u2640', u'\U0001f64d\U0001f3fe']),
            ('u1f64d_1f3ff_200d_2640.png', [u'\U0001f64d\U0001f3ff\u200d\u2640', u'\U0001f64d\U0001f3ff']),
            ]),

        (None, [
            ('u1f64d_200d_2642.png', [u'\U0001f64d\u200d\u2642']),
            ('u1f64d_1f3fb_200d_2642.png', [u'\U0001f64d\U0001f3fb\u200d\u2642']),
            ('u1f64d_1f3fc_200d_2642.png', [u'\U0001f64d\U0001f3fc\u200d\u2642']),
            ('u1f64d_1f3fd_200d_2642.png', [u'\U0001f64d\U0001f3fd\u200d\u2642']),
            ('u1f64d_1f3fe_200d_2642.png', [u'\U0001f64d\U0001f3fe\u200d\u2642']),
            ('u1f64d_1f3ff_200d_2642.png', [u'\U0001f64d\U0001f3ff\u200d\u2642']),
            ]),

        (None, [
            ('u1f64e_200d_2640.png', [u'\U0001f64e\u200d\u2640', u'\U0001f64e']),
            ('u1f64e_1f3fb_200d_2640.png', [u'\U0001f64e\U0001f3fb\u200d\u2640', u'\U0001f64e\U0001f3fb']),
            ('u1f64e_1f3fc_200d_2640.png', [u'\U0001f64e\U0001f3fc\u200d\u2640', u'\U0001f64e\U0001f3fc']),
            ('u1f64e_1f3fd_200d_2640.png', [u'\U0001f64e\U0001f3fd\u200d\u2640', u'\U0001f64e\U0001f3fd']),
            ('u1f64e_1f3fe_200d_2640.png', [u'\U0001f64e\U0001f3fe\u200d\u2640', u'\U0001f64e\U0001f3fe']),
            ('u1f64e_1f3ff_200d_2640.png', [u'\U0001f64e\U0001f3ff\u200d\u2640', u'\U0001f64e\U0001f3ff']),
            ]),

        (None, [
            ('u1f64e_200d_2642.png', [u'\U0001f64e\u200d\u2642']),
            ('u1f64e_1f3fb_200d_2642.png', [u'\U0001f64e\U0001f3fb\u200d\u2642']),
            ('u1f64e_1f3fc_200d_2642.png', [u'\U0001f64e\U0001f3fc\u200d\u2642']),
            ('u1f64e_1f3fd_200d_2642.png', [u'\U0001f64e\U0001f3fd\u200d\u2642']),
            ('u1f64e_1f3fe_200d_2642.png', [u'\U0001f64e\U0001f3fe\u200d\u2642']),
            ('u1f64e_1f3ff_200d_2642.png', [u'\U0001f64e\U0001f3ff\u200d\u2642']),
            ]),

        (None, [
            ('u1f645_200d_2640.png', [u'\U0001f645\u200d\u2640', u'\U0001f645']),
            ('u1f645_1f3fb_200d_2640.png', [u'\U0001f645\U0001f3fb\u200d\u2640', u'\U0001f645\U0001f3fb']),
            ('u1f645_1f3fc_200d_2640.png', [u'\U0001f645\U0001f3fc\u200d\u2640', u'\U0001f645\U0001f3fc']),
            ('u1f645_1f3fd_200d_2640.png', [u'\U0001f645\U0001f3fd\u200d\u2640', u'\U0001f645\U0001f3fd']),
            ('u1f645_1f3fe_200d_2640.png', [u'\U0001f645\U0001f3fe\u200d\u2640', u'\U0001f645\U0001f3fe']),
            ('u1f645_1f3ff_200d_2640.png', [u'\U0001f645\U0001f3ff\u200d\u2640', u'\U0001f645\U0001f3ff']),
            ]),

        (None, [
            ('u1f645_200d_2642.png', [u'\U0001f645\u200d\u2642']),
            ('u1f645_1f3fb_200d_2642.png', [u'\U0001f645\U0001f3fb\u200d\u2642']),
            ('u1f645_1f3fc_200d_2642.png', [u'\U0001f645\U0001f3fc\u200d\u2642']),
            ('u1f645_1f3fd_200d_2642.png', [u'\U0001f645\U0001f3fd\u200d\u2642']),
            ('u1f645_1f3fe_200d_2642.png', [u'\U0001f645\U0001f3fe\u200d\u2642']),
            ('u1f645_1f3ff_200d_2642.png', [u'\U0001f645\U0001f3ff\u200d\u2642']),
            ]),

        (None, [
            ('u1f646_200d_2640.png', [u'\U0001f646\u200d\u2640', u'\U0001f646']),
            ('u1f646_1f3fb_200d_2640.png', [u'\U0001f646\U0001f3fb\u200d\u2640', u'\U0001f646\U0001f3fb']),
            ('u1f646_1f3fc_200d_2640.png', [u'\U0001f646\U0001f3fc\u200d\u2640', u'\U0001f646\U0001f3fc']),
            ('u1f646_1f3fd_200d_2640.png', [u'\U0001f646\U0001f3fd\u200d\u2640', u'\U0001f646\U0001f3fd']),
            ('u1f646_1f3fe_200d_2640.png', [u'\U0001f646\U0001f3fe\u200d\u2640', u'\U0001f646\U0001f3fe']),
            ('u1f646_1f3ff_200d_2640.png', [u'\U0001f646\U0001f3ff\u200d\u2640', u'\U0001f646\U0001f3ff']),
            ]),

        (None, [
            ('u1f646_200d_2642.png', [u'\U0001f646\u200d\u2642']),
            ('u1f646_1f3fb_200d_2642.png', [u'\U0001f646\U0001f3fb\u200d\u2642']),
            ('u1f646_1f3fc_200d_2642.png', [u'\U0001f646\U0001f3fc\u200d\u2642']),
            ('u1f646_1f3fd_200d_2642.png', [u'\U0001f646\U0001f3fd\u200d\u2642']),
            ('u1f646_1f3fe_200d_2642.png', [u'\U0001f646\U0001f3fe\u200d\u2642']),
            ('u1f646_1f3ff_200d_2642.png', [u'\U0001f646\U0001f3ff\u200d\u2642']),
            ]),

        (None, [
            ('u1f481_200d_2640.png', [u'\U0001f481\u200d\u2640', u'\U0001f481']),
            ('u1f481_1f3fb_200d_2640.png', [u'\U0001f481\U0001f3fb\u200d\u2640', u'\U0001f481\U0001f3fb']),
            ('u1f481_1f3fc_200d_2640.png', [u'\U0001f481\U0001f3fc\u200d\u2640', u'\U0001f481\U0001f3fc']),
            ('u1f481_1f3fd_200d_2640.png', [u'\U0001f481\U0001f3fd\u200d\u2640', u'\U0001f481\U0001f3fd']),
            ('u1f481_1f3fe_200d_2640.png', [u'\U0001f481\U0001f3fe\u200d\u2640', u'\U0001f481\U0001f3fe']),
            ('u1f481_1f3ff_200d_2640.png', [u'\U0001f481\U0001f3ff\u200d\u2640', u'\U0001f481\U0001f3ff']),
            ]),

        (None, [
            ('u1f481_200d_2642.png', [u'\U0001f481\u200d\u2642']),
            ('u1f481_1f3fb_200d_2642.png', [u'\U0001f481\U0001f3fb\u200d\u2642']),
            ('u1f481_1f3fc_200d_2642.png', [u'\U0001f481\U0001f3fc\u200d\u2642']),
            ('u1f481_1f3fd_200d_2642.png', [u'\U0001f481\U0001f3fd\u200d\u2642']),
            ('u1f481_1f3fe_200d_2642.png', [u'\U0001f481\U0001f3fe\u200d\u2642']),
            ('u1f481_1f3ff_200d_2642.png', [u'\U0001f481\U0001f3ff\u200d\u2642']),
            ]),

        (None, [
            ('u1f64b_200d_2640.png', [u'\U0001f64b\u200d\u2640', u'\U0001f64b']),
            ('u1f64b_1f3fb_200d_2640.png', [u'\U0001f64b\U0001f3fb\u200d\u2640', u'\U0001f64b\U0001f3fb']),
            ('u1f64b_1f3fc_200d_2640.png', [u'\U0001f64b\U0001f3fc\u200d\u2640', u'\U0001f64b\U0001f3fc']),
            ('u1f64b_1f3fd_200d_2640.png', [u'\U0001f64b\U0001f3fd\u200d\u2640', u'\U0001f64b\U0001f3fd']),
            ('u1f64b_1f3fe_200d_2640.png', [u'\U0001f64b\U0001f3fe\u200d\u2640', u'\U0001f64b\U0001f3fe']),
            ('u1f64b_1f3ff_200d_2640.png', [u'\U0001f64b\U0001f3ff\u200d\u2640', u'\U0001f64b\U0001f3ff']),
            ]),

        (None, [
            ('u1f64b_200d_2642.png', [u'\U0001f64b\u200d\u2642']),
            ('u1f64b_1f3fb_200d_2642.png', [u'\U0001f64b\U0001f3fb\u200d\u2642']),
            ('u1f64b_1f3fc_200d_2642.png', [u'\U0001f64b\U0001f3fc\u200d\u2642']),
            ('u1f64b_1f3fd_200d_2642.png', [u'\U0001f64b\U0001f3fd\u200d\u2642']),
            ('u1f64b_1f3fe_200d_2642.png', [u'\U0001f64b\U0001f3fe\u200d\u2642']),
            ('u1f64b_1f3ff_200d_2642.png', [u'\U0001f64b\U0001f3ff\u200d\u2642']),
            ]),

        (None, [
            ('u1f647_200d_2640.png', [u'\U0001f647\u200d\u2640']),
            ('u1f647_1f3fb_200d_2640.png', [u'\U0001f647\U0001f3fb\u200d\u2640']),
            ('u1f647_1f3fc_200d_2640.png', [u'\U0001f647\U0001f3fc\u200d\u2640']),
            ('u1f647_1f3fd_200d_2640.png', [u'\U0001f647\U0001f3fd\u200d\u2640']),
            ('u1f647_1f3fe_200d_2640.png', [u'\U0001f647\U0001f3fe\u200d\u2640']),
            ('u1f647_1f3ff_200d_2640.png', [u'\U0001f647\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f647_200d_2642.png', [u'\U0001f647\u200d\u2642', u'\U0001f647']),
            ('u1f647_1f3fb_200d_2642.png', [u'\U0001f647\U0001f3fb\u200d\u2642', u'\U0001f647\U0001f3fb']),
            ('u1f647_1f3fc_200d_2642.png', [u'\U0001f647\U0001f3fc\u200d\u2642', u'\U0001f647\U0001f3fc']),
            ('u1f647_1f3fd_200d_2642.png', [u'\U0001f647\U0001f3fd\u200d\u2642', u'\U0001f647\U0001f3fd']),
            ('u1f647_1f3fe_200d_2642.png', [u'\U0001f647\U0001f3fe\u200d\u2642', u'\U0001f647\U0001f3fe']),
            ('u1f647_1f3ff_200d_2642.png', [u'\U0001f647\U0001f3ff\u200d\u2642', u'\U0001f647\U0001f3ff']),
            ]),

        (None, [
            ('u1f926_200d_2640.png', [u'\U0001f926\u200d\u2640', u'\U0001f926']),
            ('u1f926_1f3fb_200d_2640.png', [u'\U0001f926\U0001f3fb\u200d\u2640', u'\U0001f926\U0001f3fb']),
            ('u1f926_1f3fc_200d_2640.png', [u'\U0001f926\U0001f3fc\u200d\u2640', u'\U0001f926\U0001f3fc']),
            ('u1f926_1f3fd_200d_2640.png', [u'\U0001f926\U0001f3fd\u200d\u2640', u'\U0001f926\U0001f3fd']),
            ('u1f926_1f3fe_200d_2640.png', [u'\U0001f926\U0001f3fe\u200d\u2640', u'\U0001f926\U0001f3fe']),
            ('u1f926_1f3ff_200d_2640.png', [u'\U0001f926\U0001f3ff\u200d\u2640', u'\U0001f926\U0001f3ff']),
            ]),

        (None, [
            ('u1f926_200d_2642.png', [u'\U0001f926\u200d\u2642']),
            ('u1f926_1f3fb_200d_2642.png', [u'\U0001f926\U0001f3fb\u200d\u2642']),
            ('u1f926_1f3fc_200d_2642.png', [u'\U0001f926\U0001f3fc\u200d\u2642']),
            ('u1f926_1f3fd_200d_2642.png', [u'\U0001f926\U0001f3fd\u200d\u2642']),
            ('u1f926_1f3fe_200d_2642.png', [u'\U0001f926\U0001f3fe\u200d\u2642']),
            ('u1f926_1f3ff_200d_2642.png', [u'\U0001f926\U0001f3ff\u200d\u2642']),
            ]),

        (None, [
            ('u1f937_200d_2640.png', [u'\U0001f937\u200d\u2640', u'\U0001f937']),
            ('u1f937_1f3fb_200d_2640.png', [u'\U0001f937\U0001f3fb\u200d\u2640', u'\U0001f937\U0001f3fb']),
            ('u1f937_1f3fc_200d_2640.png', [u'\U0001f937\U0001f3fc\u200d\u2640', u'\U0001f937\U0001f3fc']),
            ('u1f937_1f3fd_200d_2640.png', [u'\U0001f937\U0001f3fd\u200d\u2640', u'\U0001f937\U0001f3fd']),
            ('u1f937_1f3fe_200d_2640.png', [u'\U0001f937\U0001f3fe\u200d\u2640', u'\U0001f937\U0001f3fe']),
            ('u1f937_1f3ff_200d_2640.png', [u'\U0001f937\U0001f3ff\u200d\u2640', u'\U0001f937\U0001f3ff']),
            ]),

        (None, [
            ('u1f937_200d_2642.png', [u'\U0001f937\u200d\u2642']),
            ('u1f937_1f3fb_200d_2642.png', [u'\U0001f937\U0001f3fb\u200d\u2642']),
            ('u1f937_1f3fc_200d_2642.png', [u'\U0001f937\U0001f3fc\u200d\u2642']),
            ('u1f937_1f3fd_200d_2642.png', [u'\U0001f937\U0001f3fd\u200d\u2642']),
            ('u1f937_1f3fe_200d_2642.png', [u'\U0001f937\U0001f3fe\u200d\u2642']),
            ('u1f937_1f3ff_200d_2642.png', [u'\U0001f937\U0001f3ff\u200d\u2642']),
            ]),

        # subgroup: person-activity
        (None, [
            ('u1f486_200d_2640.png', [u'\U0001f486\u200d\u2640', u'\U0001f486']),
            ('u1f486_1f3fb_200d_2640.png', [u'\U0001f486\U0001f3fb\u200d\u2640', u'\U0001f486\U0001f3fb']),
            ('u1f486_1f3fc_200d_2640.png', [u'\U0001f486\U0001f3fc\u200d\u2640', u'\U0001f486\U0001f3fc']),
            ('u1f486_1f3fd_200d_2640.png', [u'\U0001f486\U0001f3fd\u200d\u2640', u'\U0001f486\U0001f3fd']),
            ('u1f486_1f3fe_200d_2640.png', [u'\U0001f486\U0001f3fe\u200d\u2640', u'\U0001f486\U0001f3fe']),
            ('u1f486_1f3ff_200d_2640.png', [u'\U0001f486\U0001f3ff\u200d\u2640', u'\U0001f486\U0001f3ff']),
            ]),

        (None, [
            ('u1f486_200d_2642.png', [u'\U0001f486\u200d\u2642']),
            ('u1f486_1f3fb_200d_2642.png', [u'\U0001f486\U0001f3fb\u200d\u2642']),
            ('u1f486_1f3fc_200d_2642.png', [u'\U0001f486\U0001f3fc\u200d\u2642']),
            ('u1f486_1f3fd_200d_2642.png', [u'\U0001f486\U0001f3fd\u200d\u2642']),
            ('u1f486_1f3fe_200d_2642.png', [u'\U0001f486\U0001f3fe\u200d\u2642']),
            ('u1f486_1f3ff_200d_2642.png', [u'\U0001f486\U0001f3ff\u200d\u2642']),
            ]),

        (None, [
            ('u1f487_200d_2640.png', [u'\U0001f487\u200d\u2640', u'\U0001f487']),
            ('u1f487_1f3fb_200d_2640.png', [u'\U0001f487\U0001f3fb\u200d\u2640', u'\U0001f487\U0001f3fb']),
            ('u1f487_1f3fc_200d_2640.png', [u'\U0001f487\U0001f3fc\u200d\u2640', u'\U0001f487\U0001f3fd']),
            ('u1f487_1f3fd_200d_2640.png', [u'\U0001f487\U0001f3fd\u200d\u2640', u'\U0001f487\U0001f3fd']),
            ('u1f487_1f3fe_200d_2640.png', [u'\U0001f487\U0001f3fe\u200d\u2640', u'\U0001f487\U0001f3fe']),
            ('u1f487_1f3ff_200d_2640.png', [u'\U0001f487\U0001f3ff\u200d\u2640', u'\U0001f487\U0001f3ff']),
            ]),

        (None, [
            ('u1f487_200d_2642.png', [u'\U0001f487\u200d\u2642']),
            ('u1f487_1f3fb_200d_2642.png', [u'\U0001f487\U0001f3fb\u200d\u2642']),
            ('u1f487_1f3fc_200d_2642.png', [u'\U0001f487\U0001f3fc\u200d\u2642']),
            ('u1f487_1f3fd_200d_2642.png', [u'\U0001f487\U0001f3fd\u200d\u2642']),
            ('u1f487_1f3fe_200d_2642.png', [u'\U0001f487\U0001f3fe\u200d\u2642']),
            ('u1f487_1f3ff_200d_2642.png', [u'\U0001f487\U0001f3ff\u200d\u2642']),
            ]),

        (None, [
            ('u1f6b6_200d_2640.png', [u'\U0001f6b6\u200d\u2640']),
            ('u1f6b6_1f3fb_200d_2640.png', [u'\U0001f6b6\U0001f3fb\u200d\u2640']),
            ('u1f6b6_1f3fc_200d_2640.png', [u'\U0001f6b6\U0001f3fc\u200d\u2640']),
            ('u1f6b6_1f3fd_200d_2640.png', [u'\U0001f6b6\U0001f3fd\u200d\u2640']),
            ('u1f6b6_1f3fe_200d_2640.png', [u'\U0001f6b6\U0001f3fe\u200d\u2640']),
            ('u1f6b6_1f3ff_200d_2640.png', [u'\U0001f6b6\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f6b6_200d_2642.png', [u'\U0001f6b6\u200d\u2642', u'\U0001f6b6']),
            ('u1f6b6_1f3fb_200d_2642.png', [u'\U0001f6b6\U0001f3fb\u200d\u2642', u'\U0001f6b6\U0001f3fb']),
            ('u1f6b6_1f3fc_200d_2642.png', [u'\U0001f6b6\U0001f3fc\u200d\u2642', u'\U0001f6b6\U0001f3fc']),
            ('u1f6b6_1f3fd_200d_2642.png', [u'\U0001f6b6\U0001f3fd\u200d\u2642', u'\U0001f6b6\U0001f3fd']),
            ('u1f6b6_1f3fe_200d_2642.png', [u'\U0001f6b6\U0001f3fe\u200d\u2642', u'\U0001f6b6\U0001f3fe']),
            ('u1f6b6_1f3ff_200d_2642.png', [u'\U0001f6b6\U0001f3ff\u200d\u2642', u'\U0001f6b6\U0001f3ff']),
            ]),

        (None, [
            ('u1f3c3_200d_2640.png', [u'\U0001f3c3\u200d\u2640']),
            ('u1f3c3_1f3fb_200d_2640.png', [u'\U0001f3c3\U0001f3fb\u200d\u2640']),
            ('u1f3c3_1f3fc_200d_2640.png', [u'\U0001f3c3\U0001f3fc\u200d\u2640']),
            ('u1f3c3_1f3fd_200d_2640.png', [u'\U0001f3c3\U0001f3fd\u200d\u2640']),
            ('u1f3c3_1f3fe_200d_2640.png', [u'\U0001f3c3\U0001f3fe\u200d\u2640']),
            ('u1f3c3_1f3ff_200d_2640.png', [u'\U0001f3c3\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f3c3_200d_2642.png', [u'\U0001f3c3\u200d\u2642', u'\U0001f3c3']),
            ('u1f3c3_1f3fb_200d_2642.png', [u'\U0001f3c3\U0001f3fb\u200d\u2642', u'\U0001f3c3\U0001f3fb']),
            ('u1f3c3_1f3fc_200d_2642.png', [u'\U0001f3c3\U0001f3fc\u200d\u2642', u'\U0001f3c3\U0001f3fc']),
            ('u1f3c3_1f3fd_200d_2642.png', [u'\U0001f3c3\U0001f3fd\u200d\u2642', u'\U0001f3c3\U0001f3fd']),
            ('u1f3c3_1f3fe_200d_2642.png', [u'\U0001f3c3\U0001f3fe\u200d\u2642', u'\U0001f3c3\U0001f3fe']),
            ('u1f3c3_1f3ff_200d_2642.png', [u'\U0001f3c3\U0001f3ff\u200d\u2642', u'\U0001f3c3\U0001f3ff']),
            ]),

        (None, [
            ('u1f483.png', [u'\U0001f483']),
            ('u1f483_1f3fb.png', [u'\U0001f483\U0001f3fb']),
            ('u1f483_1f3fc.png', [u'\U0001f483\U0001f3fc']),
            ('u1f483_1f3fd.png', [u'\U0001f483\U0001f3fd']),
            ('u1f483_1f3fe.png', [u'\U0001f483\U0001f3fe']),
            ('u1f483_1f3ff.png', [u'\U0001f483\U0001f3ff']),
            ]),

        (None, [
            ('u1f57a.png', [u'\U0001f57a']),
            ('u1f57a_1f3fb.png', [u'\U0001f57a\U0001f3fb']),
            ('u1f57a_1f3fc.png', [u'\U0001f57a\U0001f3fc']),
            ('u1f57a_1f3fd.png', [u'\U0001f57a\U0001f3fd']),
            ('u1f57a_1f3fe.png', [u'\U0001f57a\U0001f3fe']),
            ('u1f57a_1f3ff.png', [u'\U0001f57a\U0001f3ff']),
            ]),

        ('u1f46f_200d_2640.png', [u'\U0001f46f\u200d\u2640', u'\U0001f46f']),
        ('u1f46f_200d_2642.png', [u'\U0001f46f\u200d\u2642']),

        (None, [
            ('u1f6c0.png', [u'\U0001f6c0']),
            ('u1f6c0_1f3fb.png', [u'\U0001f6c0\U0001f3fb']),
            ('u1f6c0_1f3fc.png', [u'\U0001f6c0\U0001f3fc']),
            ('u1f6c0_1f3fd.png', [u'\U0001f6c0\U0001f3fd']),
            ('u1f6c0_1f3fe.png', [u'\U0001f6c0\U0001f3fe']),
            ('u1f6c0_1f3ff.png', [u'\U0001f6c0\U0001f3ff']),
            ]),

        ('u1f6cc.png', [u'\U0001f6cc']),
        ('u1f574.png', [u'\U0001f574']),
        ('u1f5e3.png', [u'\U0001f5e3']),
        ('u1f464.png', [u'\U0001f464']),
        ('u1f465.png', [u'\U0001f465']),

        # subgroup: person-sport
        ('u1f93a.png', [u'\U0001f93a']),
        ('u1f3c7.png', [u'\U0001f3c7']),
        ('u26f7.png', [u'\u26f7']),
        ('u1f3c2.png', [u'\U0001f3c2']),
        ('u1f3cc_200d_2640.png', [u'\U0001f3cc\u200d\u2640']),
        ('u1f3cc_200d_2642.png', [u'\U0001f3cc\u200d\u2642', u'\U0001f3cc']),

        (None, [
            ('u1f3c4_200d_2640.png', [u'\U0001f3c4\u200d\u2640']),
            ('u1f3c4_1f3fb_200d_2640.png', [u'\U0001f3c4\U0001f3fb\u200d\u2640']),
            ('u1f3c4_1f3fc_200d_2640.png', [u'\U0001f3c4\U0001f3fc\u200d\u2640']),
            ('u1f3c4_1f3fd_200d_2640.png', [u'\U0001f3c4\U0001f3fd\u200d\u2640']),
            ('u1f3c4_1f3fe_200d_2640.png', [u'\U0001f3c4\U0001f3fe\u200d\u2640']),
            ('u1f3c4_1f3ff_200d_2640.png', [u'\U0001f3c4\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f3c4_200d_2642.png', [u'\U0001f3c4\u200d\u2642', u'\U0001f3c4']),
            ('u1f3c4_1f3fb_200d_2642.png', [u'\U0001f3c4\U0001f3fb\u200d\u2642', u'\U0001f3c4\U0001f3fb']),
            ('u1f3c4_1f3fc_200d_2642.png', [u'\U0001f3c4\U0001f3fc\u200d\u2642', u'\U0001f3c4\U0001f3fc']),
            ('u1f3c4_1f3fd_200d_2642.png', [u'\U0001f3c4\U0001f3fd\u200d\u2642', u'\U0001f3c4\U0001f3fd']),
            ('u1f3c4_1f3fe_200d_2642.png', [u'\U0001f3c4\U0001f3fe\u200d\u2642', u'\U0001f3c4\U0001f3fe']),
            ('u1f3c4_1f3ff_200d_2642.png', [u'\U0001f3c4\U0001f3ff\u200d\u2642', u'\U0001f3c4\U0001f3ff']),
            ]),

        (None, [
            ('u1f6a3_200d_2640.png', [u'\U0001f6a3\u200d\u2640']),
            ('u1f6a3_1f3fb_200d_2640.png', [u'\U0001f6a3\U0001f3fb\u200d\u2640']),
            ('u1f6a3_1f3fc_200d_2640.png', [u'\U0001f6a3\U0001f3fc\u200d\u2640']),
            ('u1f6a3_1f3fd_200d_2640.png', [u'\U0001f6a3\U0001f3fd\u200d\u2640']),
            ('u1f6a3_1f3fe_200d_2640.png', [u'\U0001f6a3\U0001f3fe\u200d\u2640']),
            ('u1f6a3_1f3ff_200d_2640.png', [u'\U0001f6a3\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f6a3_200d_2642.png', [u'\U0001f6a3\u200d\u2642', u'\U0001f6a3']),
            ('u1f6a3_1f3fb_200d_2642.png', [u'\U0001f6a3\U0001f3fb\u200d\u2642', u'\U0001f6a3\U0001f3fb']),
            ('u1f6a3_1f3fc_200d_2642.png', [u'\U0001f6a3\U0001f3fc\u200d\u2642', u'\U0001f6a3\U0001f3fc']),
            ('u1f6a3_1f3fd_200d_2642.png', [u'\U0001f6a3\U0001f3fd\u200d\u2642', u'\U0001f6a3\U0001f3fd']),
            ('u1f6a3_1f3fe_200d_2642.png', [u'\U0001f6a3\U0001f3fe\u200d\u2642', u'\U0001f6a3\U0001f3fe']),
            ('u1f6a3_1f3ff_200d_2642.png', [u'\U0001f6a3\U0001f3ff\u200d\u2642', u'\U0001f6a3\U0001f3ff']),
            ]),

        (None, [
            ('u1f3ca_200d_2640.png', [u'\U0001f3ca\u200d\u2640']),
            ('u1f3ca_1f3fb_200d_2640.png', [u'\U0001f3ca\U0001f3fb\u200d\u2640']),
            ('u1f3ca_1f3fc_200d_2640.png', [u'\U0001f3ca\U0001f3fc\u200d\u2640']),
            ('u1f3ca_1f3fd_200d_2640.png', [u'\U0001f3ca\U0001f3fd\u200d\u2640']),
            ('u1f3ca_1f3fe_200d_2640.png', [u'\U0001f3ca\U0001f3fe\u200d\u2640']),
            ('u1f3ca_1f3ff_200d_2640.png', [u'\U0001f3ca\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f3ca_200d_2642.png', [u'\U0001f3ca\u200d\u2642', u'\U0001f3ca']),
            ('u1f3ca_1f3fb_200d_2642.png', [u'\U0001f3ca\U0001f3fb\u200d\u2642', u'\U0001f3ca\U0001f3fb']),
            ('u1f3ca_1f3fc_200d_2642.png', [u'\U0001f3ca\U0001f3fc\u200d\u2642', u'\U0001f3ca\U0001f3fc']),
            ('u1f3ca_1f3fd_200d_2642.png', [u'\U0001f3ca\U0001f3fd\u200d\u2642', u'\U0001f3ca\U0001f3fd']),
            ('u1f3ca_1f3fe_200d_2642.png', [u'\U0001f3ca\U0001f3fe\u200d\u2642', u'\U0001f3ca\U0001f3fe']),
            ('u1f3ca_1f3ff_200d_2642.png', [u'\U0001f3ca\U0001f3ff\u200d\u2642', u'\U0001f3ca\U0001f3ff']),
            ]),

        (None, [
            ('u26f9_200d_2640.png', [u'\u26f9\u200d\u2640']),
            ('u26f9_1f3fb_200d_2640.png', [u'\u26f9\U0001f3fb\u200d\u2640']),
            ('u26f9_1f3fc_200d_2640.png', [u'\u26f9\U0001f3fc\u200d\u2640']),
            ('u26f9_1f3fd_200d_2640.png', [u'\u26f9\U0001f3fd\u200d\u2640']),
            ('u26f9_1f3fe_200d_2640.png', [u'\u26f9\U0001f3fe\u200d\u2640']),
            ('u26f9_1f3ff_200d_2640.png', [u'\u26f9\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u26f9_200d_2642.png', [u'\u26f9\u200d\u2642', u'\u26f9']),
            ('u26f9_1f3fb_200d_2642.png', [u'\u26f9\U0001f3fb\u200d\u2642', u'\u26f9\U0001f3fb']),
            ('u26f9_1f3fc_200d_2642.png', [u'\u26f9\U0001f3fc\u200d\u2642', u'\u26f9\U0001f3fc']),
            ('u26f9_1f3fd_200d_2642.png', [u'\u26f9\U0001f3fd\u200d\u2642', u'\u26f9\U0001f3fd']),
            ('u26f9_1f3fe_200d_2642.png', [u'\u26f9\U0001f3fe\u200d\u2642', u'\u26f9\U0001f3fe']),
            ('u26f9_1f3ff_200d_2642.png', [u'\u26f9\U0001f3ff\u200d\u2642', u'\u26f9\U0001f3ff']),
            ]),

        (None, [
            ('u1f3cb_200d_2640.png', [u'\U0001f3cb\u200d\u2640']),
            ('u1f3cb_1f3fb_200d_2640.png', [u'\U0001f3cb\U0001f3fb\u200d\u2640']),
            ('u1f3cb_1f3fc_200d_2640.png', [u'\U0001f3cb\U0001f3fc\u200d\u2640']),
            ('u1f3cb_1f3fd_200d_2640.png', [u'\U0001f3cb\U0001f3fd\u200d\u2640']),
            ('u1f3cb_1f3fe_200d_2640.png', [u'\U0001f3cb\U0001f3fe\u200d\u2640']),
            ('u1f3cb_1f3ff_200d_2640.png', [u'\U0001f3cb\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f3cb_200d_2642.png', [u'\U0001f3cb\u200d\u2642', u'\U0001f3cb']),
            ('u1f3cb_1f3fb_200d_2642.png', [u'\U0001f3cb\U0001f3fb\u200d\u2642', u'\U0001f3cb\U0001f3fb']),
            ('u1f3cb_1f3fc_200d_2642.png', [u'\U0001f3cb\U0001f3fc\u200d\u2642', u'\U0001f3cb\U0001f3fc']),
            ('u1f3cb_1f3fd_200d_2642.png', [u'\U0001f3cb\U0001f3fd\u200d\u2642', u'\U0001f3cb\U0001f3fd']),
            ('u1f3cb_1f3fe_200d_2642.png', [u'\U0001f3cb\U0001f3fe\u200d\u2642', u'\U0001f3cb\U0001f3fe']),
            ('u1f3cb_1f3ff_200d_2642.png', [u'\U0001f3cb\U0001f3ff\u200d\u2642', u'\U0001f3cb\U0001f3ff']),
            ]),

        (None, [
            ('u1f6b4_200d_2640.png', [u'\U0001f6b4\u200d\u2640']),
            ('u1f6b4_1f3fb_200d_2640.png', [u'\U0001f6b4\U0001f3fb\u200d\u2640']),
            ('u1f6b4_1f3fc_200d_2640.png', [u'\U0001f6b4\U0001f3fc\u200d\u2640']),
            ('u1f6b4_1f3fd_200d_2640.png', [u'\U0001f6b4\U0001f3fd\u200d\u2640']),
            ('u1f6b4_1f3fe_200d_2640.png', [u'\U0001f6b4\U0001f3fe\u200d\u2640']),
            ('u1f6b4_1f3ff_200d_2640.png', [u'\U0001f6b4\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f6b4_200d_2642.png', [u'\U0001f6b4\u200d\u2642', u'\U0001f6b4']),
            ('u1f6b4_1f3fb_200d_2642.png', [u'\U0001f6b4\U0001f3fb\u200d\u2642', u'\U0001f6b4\U0001f3fb']),
            ('u1f6b4_1f3fc_200d_2642.png', [u'\U0001f6b4\U0001f3fc\u200d\u2642', u'\U0001f6b4\U0001f3fc']),
            ('u1f6b4_1f3fd_200d_2642.png', [u'\U0001f6b4\U0001f3fd\u200d\u2642', u'\U0001f6b4\U0001f3fd']),
            ('u1f6b4_1f3fe_200d_2642.png', [u'\U0001f6b4\U0001f3fe\u200d\u2642', u'\U0001f6b4\U0001f3fe']),
            ('u1f6b4_1f3ff_200d_2642.png', [u'\U0001f6b4\U0001f3ff\u200d\u2642', u'\U0001f6b4\U0001f3ff']),
            ]),

        (None, [
            ('u1f6b5_200d_2640.png', [u'\U0001f6b5\u200d\u2640']),
            ('u1f6b5_1f3fb_200d_2640.png', [u'\U0001f6b5\U0001f3fb\u200d\u2640']),
            ('u1f6b5_1f3fc_200d_2640.png', [u'\U0001f6b5\U0001f3fc\u200d\u2640']),
            ('u1f6b5_1f3fd_200d_2640.png', [u'\U0001f6b5\U0001f3fd\u200d\u2640']),
            ('u1f6b5_1f3fe_200d_2640.png', [u'\U0001f6b5\U0001f3fe\u200d\u2640']),
            ('u1f6b5_1f3ff_200d_2640.png', [u'\U0001f6b5\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f6b5_200d_2642.png', [u'\U0001f6b5\u200d\u2642', u'\U0001f6b5']),
            ('u1f6b5_1f3fb_200d_2642.png', [u'\U0001f6b5\U0001f3fb\u200d\u2642', u'\U0001f6b5\U0001f3fb']),
            ('u1f6b5_1f3fc_200d_2642.png', [u'\U0001f6b5\U0001f3fc\u200d\u2642', u'\U0001f6b5\U0001f3fc']),
            ('u1f6b5_1f3fd_200d_2642.png', [u'\U0001f6b5\U0001f3fd\u200d\u2642', u'\U0001f6b5\U0001f3fd']),
            ('u1f6b5_1f3fe_200d_2642.png', [u'\U0001f6b5\U0001f3fe\u200d\u2642', u'\U0001f6b5\U0001f3fe']),
            ('u1f6b5_1f3ff_200d_2642.png', [u'\U0001f6b5\U0001f3ff\u200d\u2642', u'\U0001f6b5\U0001f3ff']),
            ]),

        ('u1f3ce.png', [u'\U0001f3ce']),
        ('u1f3cd.png', [u'\U0001f3cd']),

        (None, [
            ('u1f938_200d_2640.png', [u'\U0001f938\u200d\u2640']),
            ('u1f938_1f3fb_200d_2640.png', [u'\U0001f938\U0001f3fb\u200d\u2640']),
            ('u1f938_1f3fc_200d_2640.png', [u'\U0001f938\U0001f3fc\u200d\u2640']),
            ('u1f938_1f3fd_200d_2640.png', [u'\U0001f938\U0001f3fd\u200d\u2640']),
            ('u1f938_1f3fe_200d_2640.png', [u'\U0001f938\U0001f3fe\u200d\u2640']),
            ('u1f938_1f3ff_200d_2640.png', [u'\U0001f938\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f938_200d_2642.png', [u'\U0001f938\u200d\u2642', u'\U0001f938']),
            ('u1f938_1f3fb_200d_2642.png', [u'\U0001f938\U0001f3fb\u200d\u2642', u'\U0001f938\U0001f3fb']),
            ('u1f938_1f3fc_200d_2642.png', [u'\U0001f938\U0001f3fc\u200d\u2642', u'\U0001f938\U0001f3fc']),
            ('u1f938_1f3fd_200d_2642.png', [u'\U0001f938\U0001f3fd\u200d\u2642', u'\U0001f938\U0001f3fd']),
            ('u1f938_1f3fe_200d_2642.png', [u'\U0001f938\U0001f3fe\u200d\u2642', u'\U0001f938\U0001f3fe']),
            ('u1f938_1f3ff_200d_2642.png', [u'\U0001f938\U0001f3ff\u200d\u2642', u'\U0001f938\U0001f3ff']),
            ]),

        (None, [
            ('u1f93c_200d_2640.png', [u'\U0001f93c\u200d\u2640']),
            ('u1f93c_1f3fb_200d_2640.png', [u'\U0001f93c\U0001f3fb\u200d\u2640']),
            ('u1f93c_1f3fc_200d_2640.png', [u'\U0001f93c\U0001f3fc\u200d\u2640']),
            ('u1f93c_1f3fd_200d_2640.png', [u'\U0001f93c\U0001f3fd\u200d\u2640']),
            ('u1f93c_1f3fe_200d_2640.png', [u'\U0001f93c\U0001f3fe\u200d\u2640']),
            ('u1f93c_1f3ff_200d_2640.png', [u'\U0001f93c\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f93c_200d_2642.png', [u'\U0001f93c\u200d\u2642', u'\U0001f93c']),
            ('u1f93c_1f3fb_200d_2642.png', [u'\U0001f93c\U0001f3fb\u200d\u2642', u'\U0001f93c\U0001f3fb']),
            ('u1f93c_1f3fc_200d_2642.png', [u'\U0001f93c\U0001f3fc\u200d\u2642', u'\U0001f93c\U0001f3fc']),
            ('u1f93c_1f3fd_200d_2642.png', [u'\U0001f93c\U0001f3fd\u200d\u2642', u'\U0001f93c\U0001f3fd']),
            ('u1f93c_1f3fe_200d_2642.png', [u'\U0001f93c\U0001f3fe\u200d\u2642', u'\U0001f93c\U0001f3fe']),
            ('u1f93c_1f3ff_200d_2642.png', [u'\U0001f93c\U0001f3ff\u200d\u2642', u'\U0001f93c\U0001f3ff']),
            ]),

        (None, [
            ('u1f93d_200d_2640.png', [u'\U0001f93d\u200d\u2640']),
            ('u1f93d_1f3fb_200d_2640.png', [u'\U0001f93d\U0001f3fb\u200d\u2640']),
            ('u1f93d_1f3fc_200d_2640.png', [u'\U0001f93d\U0001f3fc\u200d\u2640']),
            ('u1f93d_1f3fd_200d_2640.png', [u'\U0001f93d\U0001f3fd\u200d\u2640']),
            ('u1f93d_1f3fe_200d_2640.png', [u'\U0001f93d\U0001f3fe\u200d\u2640']),
            ('u1f93d_1f3ff_200d_2640.png', [u'\U0001f93d\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f93d_200d_2642.png', [u'\U0001f93d\u200d\u2642', u'\U0001f93d']),
            ('u1f93d_1f3fb_200d_2642.png', [u'\U0001f93d\U0001f3fb\u200d\u2642', u'\U0001f93d\U0001f3fb']),
            ('u1f93d_1f3fc_200d_2642.png', [u'\U0001f93d\U0001f3fc\u200d\u2642', u'\U0001f93d\U0001f3fc']),
            ('u1f93d_1f3fd_200d_2642.png', [u'\U0001f93d\U0001f3fd\u200d\u2642', u'\U0001f93d\U0001f3fd']),
            ('u1f93d_1f3fe_200d_2642.png', [u'\U0001f93d\U0001f3fe\u200d\u2642', u'\U0001f93d\U0001f3fe']),
            ('u1f93d_1f3ff_200d_2642.png', [u'\U0001f93d\U0001f3ff\u200d\u2642', u'\U0001f93d\U0001f3ff']),
            ]),

        (None, [
            ('u1f93e_200d_2640.png', [u'\U0001f93e\u200d\u2640']),
            ('u1f93e_1f3fb_200d_2640.png', [u'\U0001f93e\U0001f3fb\u200d\u2640']),
            ('u1f93e_1f3fc_200d_2640.png', [u'\U0001f93e\U0001f3fc\u200d\u2640']),
            ('u1f93e_1f3fd_200d_2640.png', [u'\U0001f93e\U0001f3fd\u200d\u2640']),
            ('u1f93e_1f3fe_200d_2640.png', [u'\U0001f93e\U0001f3fe\u200d\u2640']),
            ('u1f93e_1f3ff_200d_2640.png', [u'\U0001f93e\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f93e_200d_2642.png', [u'\U0001f93e\u200d\u2642', u'\U0001f93e']),
            ('u1f93e_1f3fb_200d_2642.png', [u'\U0001f93e\U0001f3fb\u200d\u2642', u'\U0001f93e\U0001f3fb']),
            ('u1f93e_1f3fc_200d_2642.png', [u'\U0001f93e\U0001f3fc\u200d\u2642', u'\U0001f93e\U0001f3fc']),
            ('u1f93e_1f3fd_200d_2642.png', [u'\U0001f93e\U0001f3fd\u200d\u2642', u'\U0001f93e\U0001f3fd']),
            ('u1f93e_1f3fe_200d_2642.png', [u'\U0001f93e\U0001f3fe\u200d\u2642', u'\U0001f93e\U0001f3fe']),
            ('u1f93e_1f3ff_200d_2642.png', [u'\U0001f93e\U0001f3ff\u200d\u2642', u'\U0001f93e\U0001f3ff']),
            ]),

        (None, [
            ('u1f939_200d_2640.png', [u'\U0001f939\u200d\u2640']),
            ('u1f939_1f3fb_200d_2640.png', [u'\U0001f939\U0001f3fb\u200d\u2640']),
            ('u1f939_1f3fc_200d_2640.png', [u'\U0001f939\U0001f3fc\u200d\u2640']),
            ('u1f939_1f3fd_200d_2640.png', [u'\U0001f939\U0001f3fd\u200d\u2640']),
            ('u1f939_1f3fe_200d_2640.png', [u'\U0001f939\U0001f3fe\u200d\u2640']),
            ('u1f939_1f3ff_200d_2640.png', [u'\U0001f939\U0001f3ff\u200d\u2640']),
            ]),

        (None, [
            ('u1f939_200d_2642.png', [u'\U0001f939\u200d\u2642', u'\U0001f939']),
            ('u1f939_1f3fb_200d_2642.png', [u'\U0001f939\U0001f3fb\u200d\u2642', u'\U0001f939\U0001f3fb']),
            ('u1f939_1f3fc_200d_2642.png', [u'\U0001f939\U0001f3fc\u200d\u2642', u'\U0001f939\U0001f3fc']),
            ('u1f939_1f3fd_200d_2642.png', [u'\U0001f939\U0001f3fd\u200d\u2642', u'\U0001f939\U0001f3fd']),
            ('u1f939_1f3fe_200d_2642.png', [u'\U0001f939\U0001f3fe\u200d\u2642', u'\U0001f939\U0001f3fe']),
            ('u1f939_1f3ff_200d_2642.png', [u'\U0001f939\U0001f3ff\u200d\u2642', u'\U0001f939\U0001f3ff']),
            ]),

        # subgroup: family
        (None, [
            ('u1f46b.png', [u'\U0001f46b']),
            ('u1f46c.png', [u'\U0001f46c']),
            ('u1f46d.png', [u'\U0001f46d']),
            ]),

        (None, [
            ('u1f469_200d_2764_200d_1f468.png', [u'\U0001f469\u200d\u2764\u200d\U0001f468']),
            ('u1f468_200d_2764_200d_1f468.png', [u'\U0001f468\u200d\u2764\u200d\U0001f468']),
            ('u1f469_200d_2764_200d_1f469.png', [u'\U0001f469\u200d\u2764\u200d\U0001f469']),
            ]),

        (None, [
            ('u1f469_200d_2764_200d_1f48b_200d_1f468.png', [u'\U0001f469\u200d\u2764\u200d\U0001f48b\u200d\U0001f468']),
            ('u1f468_200d_2764_200d_1f48b_200d_1f468.png', [u'\U0001f468\u200d\u2764\u200d\U0001f48b\u200d\U0001f468']),
            ('u1f469_200d_2764_200d_1f48b_200d_1f469.png', [u'\U0001f469\u200d\u2764\u200d\U0001f48b\u200d\U0001f469']),
            ]),

        (None, [
            ('u1f46a.png', [u'\U0001f46a']),
            ('u1f468_200d_1f466.png', [u'\U0001f468\u200d\U0001f466']),
            ('u1f468_200d_1f466_200d_1f466.png', [u'\U0001f468\u200d\U0001f466\u200d\U0001f466']),
            ('u1f468_200d_1f467.png', [u'\U0001f468\u200d\U0001f467']),
            ('u1f468_200d_1f467_200d_1f466.png', [u'\U0001f468\u200d\U0001f467\u200d\U0001f466']),
            ('u1f468_200d_1f467_200d_1f467.png', [u'\U0001f468\u200d\U0001f467\u200d\U0001f467']),
            ('u1f468_200d_1f468_200d_1f466.png', [u'\U0001f468\u200d\U0001f468\u200d\U0001f466']),
            ('u1f468_200d_1f468_200d_1f466_200d_1f466.png', [u'\U0001f468\u200d\U0001f468\u200d\U0001f466\u200d\U0001f466']),
            ('u1f468_200d_1f468_200d_1f467.png', [u'\U0001f468\u200d\U0001f468\u200d\U0001f467']),
            ('u1f468_200d_1f468_200d_1f467_200d_1f466.png', [u'\U0001f468\u200d\U0001f468\u200d\U0001f467\u200d\U0001f466']),
            ('u1f468_200d_1f468_200d_1f467_200d_1f467.png', [u'\U0001f468\u200d\U0001f468\u200d\U0001f467\u200d\U0001f467']),
            ('u1f468_200d_1f469_200d_1f466.png', [u'\U0001f468\u200d\U0001f469\u200d\U0001f466']),
            ('u1f468_200d_1f469_200d_1f466_200d_1f466.png', [u'\U0001f468\u200d\U0001f469\u200d\U0001f466\u200d\U0001f466']),
            ('u1f468_200d_1f469_200d_1f467.png', [u'\U0001f468\u200d\U0001f469\u200d\U0001f467']),
            ('u1f468_200d_1f469_200d_1f467_200d_1f466.png', [u'\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466']),
            ('u1f468_200d_1f469_200d_1f467_200d_1f467.png', [u'\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f467']),
            ('u1f469_200d_1f466.png', [u'\U0001f469\u200d\U0001f466']),
            ('u1f469_200d_1f466_200d_1f466.png', [u'\U0001f469\u200d\U0001f466\u200d\U0001f466']),
            ('u1f469_200d_1f467.png', [u'\U0001f469\u200d\U0001f467']),
            ('u1f469_200d_1f467_200d_1f466.png', [u'\U0001f469\u200d\U0001f467\u200d\U0001f466']),
            ('u1f469_200d_1f467_200d_1f467.png', [u'\U0001f469\u200d\U0001f467\u200d\U0001f467']),
            ('u1f469_200d_1f469_200d_1f466.png', [u'\U0001f469\u200d\U0001f469\u200d\U0001f466']),
            ('u1f469_200d_1f469_200d_1f466_200d_1f466.png', [u'\U0001f469\u200d\U0001f469\u200d\U0001f466\u200d\U0001f466']),
            ('u1f469_200d_1f469_200d_1f467.png', [u'\U0001f469\u200d\U0001f469\u200d\U0001f467']),
            ('u1f469_200d_1f469_200d_1f467_200d_1f466.png', [u'\U0001f469\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466']),
            ('u1f469_200d_1f469_200d_1f467_200d_1f467.png', [u'\U0001f469\u200d\U0001f469\u200d\U0001f467\u200d\U0001f467']),
            ]),

        # subgroup: body
        (None, [
            ('u1f933.png', [u'\U0001f933']),
            ('u1f933_1f3fb.png', [u'\U0001f933\U0001f3fb']),
            ('u1f933_1f3fc.png', [u'\U0001f933\U0001f3fc']),
            ('u1f933_1f3fd.png', [u'\U0001f933\U0001f3fd']),
            ('u1f933_1f3fe.png', [u'\U0001f933\U0001f3fe']),
            ('u1f933_1f3ff.png', [u'\U0001f933\U0001f3ff']),
            ]),


        (None, [
            ('u1f4aa.png', [u'\U0001f4aa']),
            ('u1f4aa_1f3fb.png', [u'\U0001f4aa\U0001f3fb']),
            ('u1f4aa_1f3fc.png', [u'\U0001f4aa\U0001f3fc']),
            ('u1f4aa_1f3fd.png', [u'\U0001f4aa\U0001f3fd']),
            ('u1f4aa_1f3fe.png', [u'\U0001f4aa\U0001f3fe']),
            ('u1f4aa_1f3ff.png', [u'\U0001f4aa\U0001f3ff']),
            ]),

        (None, [
            ('u1f448.png', [u'\U0001f448']),
            ('u1f448_1f3fb.png', [u'\U0001f448\U0001f3fb']),
            ('u1f448_1f3fc.png', [u'\U0001f448\U0001f3fc']),
            ('u1f448_1f3fd.png', [u'\U0001f448\U0001f3fd']),
            ('u1f448_1f3fe.png', [u'\U0001f448\U0001f3fe']),
            ('u1f448_1f3ff.png', [u'\U0001f448\U0001f3ff']),
            ]),

        (None, [
            ('u1f449.png', [u'\U0001f449']),
            ('u1f449_1f3fb.png', [u'\U0001f449\U0001f3fb']),
            ('u1f449_1f3fc.png', [u'\U0001f449\U0001f3fc']),
            ('u1f449_1f3fd.png', [u'\U0001f449\U0001f3fd']),
            ('u1f449_1f3fe.png', [u'\U0001f449\U0001f3fe']),
            ('u1f449_1f3ff.png', [u'\U0001f449\U0001f3ff']),
            ]),

        (None, [
            ('u261d.png', [u'\u261d']),
            ('u261d_1f3fb.png', [u'\u261d\U0001f3fb']),
            ('u261d_1f3fc.png', [u'\u261d\U0001f3fc']),
            ('u261d_1f3fd.png', [u'\u261d\U0001f3fd']),
            ('u261d_1f3fe.png', [u'\u261d\U0001f3fe']),
            ('u261d_1f3ff.png', [u'\u261d\U0001f3ff']),
            ]),

        (None, [
            ('u1f446.png', [u'\U0001f446']),
            ('u1f446_1f3fb.png', [u'\U0001f446\U0001f3fb']),
            ('u1f446_1f3fc.png', [u'\U0001f446\U0001f3fc']),
            ('u1f446_1f3fd.png', [u'\U0001f446\U0001f3fd']),
            ('u1f446_1f3fe.png', [u'\U0001f446\U0001f3fe']),
            ('u1f446_1f3ff.png', [u'\U0001f446\U0001f3ff']),
            ]),

        (None, [
            ('u1f595.png', [u'\U0001f595']),
            ('u1f595_1f3fb.png', [u'\U0001f595\U0001f3fb']),
            ('u1f595_1f3fc.png', [u'\U0001f595\U0001f3fc']),
            ('u1f595_1f3fd.png', [u'\U0001f595\U0001f3fd']),
            ('u1f595_1f3fe.png', [u'\U0001f595\U0001f3fe']),
            ('u1f595_1f3ff.png', [u'\U0001f595\U0001f3ff']),
            ]),

        (None, [
            ('u1f447.png', [u'\U0001f447']),
            ('u1f447_1f3fb.png', [u'\U0001f447\U0001f3fb']),
            ('u1f447_1f3fc.png', [u'\U0001f447\U0001f3fc']),
            ('u1f447_1f3fd.png', [u'\U0001f447\U0001f3fd']),
            ('u1f447_1f3fe.png', [u'\U0001f447\U0001f3fe']),
            ('u1f447_1f3ff.png', [u'\U0001f447\U0001f3ff']),
            ]),

        (None, [
            ('u270c.png', [u'\u270c']),
            ('u270c_1f3fb.png', [u'\u270c\U0001f3fb']),
            ('u270c_1f3fc.png', [u'\u270c\U0001f3fc']),
            ('u270c_1f3fd.png', [u'\u270c\U0001f3fd']),
            ('u270c_1f3fe.png', [u'\u270c\U0001f3fe']),
            ('u270c_1f3ff.png', [u'\u270c\U0001f3ff']),
            ]),

        (None, [
            ('u1f91e.png', [u'\U0001f91e']),
            ('u1f91e_1f3fb.png', [u'\U0001f91e\U0001f3fb']),
            ('u1f91e_1f3fc.png', [u'\U0001f91e\U0001f3fc']),
            ('u1f91e_1f3fd.png', [u'\U0001f91e\U0001f3fd']),
            ('u1f91e_1f3fe.png', [u'\U0001f91e\U0001f3fe']),
            ('u1f91e_1f3ff.png', [u'\U0001f91e\U0001f3ff']),
            ]),

        (None, [
            ('u1f596.png', [u'\U0001f596']),
            ('u1f596_1f3fb.png', [u'\U0001f596\U0001f3fb']),
            ('u1f596_1f3fc.png', [u'\U0001f596\U0001f3fc']),
            ('u1f596_1f3fd.png', [u'\U0001f596\U0001f3fd']),
            ('u1f596_1f3fe.png', [u'\U0001f596\U0001f3fe']),
            ('u1f596_1f3ff.png', [u'\U0001f596\U0001f3ff']),
            ]),

        (None, [
            ('u1f918.png', [u'\U0001f918']),
            ('u1f918_1f3fb.png', [u'\U0001f918\U0001f3fb']),
            ('u1f918_1f3fc.png', [u'\U0001f918\U0001f3fc']),
            ('u1f918_1f3fd.png', [u'\U0001f918\U0001f3fd']),
            ('u1f918_1f3fe.png', [u'\U0001f918\U0001f3fe']),
            ('u1f918_1f3ff.png', [u'\U0001f918\U0001f3ff']),
            ]),

        (None, [
            ('u1f919.png', [u'\U0001f919']),
            ('u1f919_1f3fb.png', [u'\U0001f919\U0001f3fb']),
            ('u1f919_1f3fc.png', [u'\U0001f919\U0001f3fc']),
            ('u1f919_1f3fd.png', [u'\U0001f919\U0001f3fd']),
            ('u1f919_1f3fe.png', [u'\U0001f919\U0001f3fe']),
            ('u1f919_1f3ff.png', [u'\U0001f919\U0001f3ff']),
            ]),

        (None, [
            ('u1f590.png', [u'\U0001f590']),
            ('u1f590_1f3fb.png', [u'\U0001f590\U0001f3fb']),
            ('u1f590_1f3fc.png', [u'\U0001f590\U0001f3fc']),
            ('u1f590_1f3fd.png', [u'\U0001f590\U0001f3fd']),
            ('u1f590_1f3fe.png', [u'\U0001f590\U0001f3fe']),
            ('u1f590_1f3ff.png', [u'\U0001f590\U0001f3ff']),
            ]),

        (None, [
            ('u270b.png', [u'\u270b']),
            ('u270b_1f3fb.png', [u'\u270b\U0001f3fb']),
            ('u270b_1f3fc.png', [u'\u270b\U0001f3fc']),
            ('u270b_1f3fd.png', [u'\u270b\U0001f3fd']),
            ('u270b_1f3fe.png', [u'\u270b\U0001f3fe']),
            ('u270b_1f3ff.png', [u'\u270b\U0001f3ff']),
            ]),

        (None, [
            ('u1f44c.png', [u'\U0001f44c']),
            ('u1f44c_1f3fb.png', [u'\U0001f44c\U0001f3fb']),
            ('u1f44c_1f3fc.png', [u'\U0001f44c\U0001f3fc']),
            ('u1f44c_1f3fd.png', [u'\U0001f44c\U0001f3fd']),
            ('u1f44c_1f3fe.png', [u'\U0001f44c\U0001f3fe']),
            ('u1f44c_1f3ff.png', [u'\U0001f44c\U0001f3ff']),
            ]),

        (None, [
            ('u1f44d.png', [u'\U0001f44d']),
            ('u1f44d_1f3fb.png', [u'\U0001f44d\U0001f3fb']),
            ('u1f44d_1f3fc.png', [u'\U0001f44d\U0001f3fc']),
            ('u1f44d_1f3fd.png', [u'\U0001f44d\U0001f3fd']),
            ('u1f44d_1f3fe.png', [u'\U0001f44d\U0001f3fe']),
            ('u1f44d_1f3ff.png', [u'\U0001f44d\U0001f3ff']),
            ]),

        (None, [
            ('u1f44e.png', [u'\U0001f44e']),
            ('u1f44e_1f3fb.png', [u'\U0001f44e\U0001f3fb']),
            ('u1f44e_1f3fc.png', [u'\U0001f44e\U0001f3fc']),
            ('u1f44e_1f3fd.png', [u'\U0001f44e\U0001f3fd']),
            ('u1f44e_1f3fe.png', [u'\U0001f44e\U0001f3fe']),
            ('u1f44e_1f3ff.png', [u'\U0001f44e\U0001f3ff']),
            ]),

        (None, [
            ('u270a.png', [u'\u270a']),
            ('u270a_1f3fb.png', [u'\u270a\U0001f3fb']),
            ('u270a_1f3fc.png', [u'\u270a\U0001f3fc']),
            ('u270a_1f3fd.png', [u'\u270a\U0001f3fd']),
            ('u270a_1f3fe.png', [u'\u270a\U0001f3fe']),
            ('u270a_1f3ff.png', [u'\u270a\U0001f3ff']),
            ]),

        (None, [
            ('u1f44a.png', [u'\U0001f44a']),
            ('u1f44a_1f3fb.png', [u'\U0001f44a\U0001f3fb']),
            ('u1f44a_1f3fc.png', [u'\U0001f44a\U0001f3fc']),
            ('u1f44a_1f3fd.png', [u'\U0001f44a\U0001f3fd']),
            ('u1f44a_1f3fe.png', [u'\U0001f44a\U0001f3fe']),
            ('u1f44a_1f3ff.png', [u'\U0001f44a\U0001f3ff']),
            ]),

        (None, [
            ('u1f91b.png', [u'\U0001f91b']),
            ('u1f91b_1f3fb.png', [u'\U0001f91b\U0001f3fb']),
            ('u1f91b_1f3fc.png', [u'\U0001f91b\U0001f3fc']),
            ('u1f91b_1f3fd.png', [u'\U0001f91b\U0001f3fd']),
            ('u1f91b_1f3fe.png', [u'\U0001f91b\U0001f3fe']),
            ('u1f91b_1f3ff.png', [u'\U0001f91b\U0001f3ff']),
            ]),

        (None, [
            ('u1f91c.png', [u'\U0001f91c']),
            ('u1f91c_1f3fb.png', [u'\U0001f91c\U0001f3fb']),
            ('u1f91c_1f3fc.png', [u'\U0001f91c\U0001f3fc']),
            ('u1f91c_1f3fd.png', [u'\U0001f91c\U0001f3fd']),
            ('u1f91c_1f3fe.png', [u'\U0001f91c\U0001f3fe']),
            ('u1f91c_1f3ff.png', [u'\U0001f91c\U0001f3ff']),
            ]),

        (None, [
            ('u1f91a.png', [u'\U0001f91a']),
            ('u1f91a_1f3fb.png', [u'\U0001f91a\U0001f3fb']),
            ('u1f91a_1f3fc.png', [u'\U0001f91a\U0001f3fc']),
            ('u1f91a_1f3fd.png', [u'\U0001f91a\U0001f3fd']),
            ('u1f91a_1f3fe.png', [u'\U0001f91a\U0001f3fe']),
            ('u1f91a_1f3ff.png', [u'\U0001f91a\U0001f3ff']),
            ]),

        (None, [
            ('u1f44b.png', [u'\U0001f44b']),
            ('u1f44b_1f3fb.png', [u'\U0001f44b\U0001f3fb']),
            ('u1f44b_1f3fc.png', [u'\U0001f44b\U0001f3fc']),
            ('u1f44b_1f3fd.png', [u'\U0001f44b\U0001f3fd']),
            ('u1f44b_1f3fe.png', [u'\U0001f44b\U0001f3fe']),
            ('u1f44b_1f3ff.png', [u'\U0001f44b\U0001f3ff']),
            ]),

        (None, [
            ('u270d.png', [u'\u270d']),
            ('u270d_1f3fb.png', [u'\u270d\U0001f3fb']),
            ('u270d_1f3fc.png', [u'\u270d\U0001f3fc']),
            ('u270d_1f3fd.png', [u'\u270d\U0001f3fd']),
            ('u270d_1f3fe.png', [u'\u270d\U0001f3fe']),
            ('u270d_1f3ff.png', [u'\u270d\U0001f3ff']),
            ]),

        (None, [
            ('u1f44f.png', [u'\U0001f44f']),
            ('u1f44f_1f3fb.png', [u'\U0001f44f\U0001f3fb']),
            ('u1f44f_1f3fc.png', [u'\U0001f44f\U0001f3fc']),
            ('u1f44f_1f3fd.png', [u'\U0001f44f\U0001f3fd']),
            ('u1f44f_1f3fe.png', [u'\U0001f44f\U0001f3fe']),
            ('u1f44f_1f3ff.png', [u'\U0001f44f\U0001f3ff']),
            ]),

        (None, [
            ('u1f450.png', [u'\U0001f450']),
            ('u1f450_1f3fb.png', [u'\U0001f450\U0001f3fb']),
            ('u1f450_1f3fc.png', [u'\U0001f450\U0001f3fc']),
            ('u1f450_1f3fd.png', [u'\U0001f450\U0001f3fd']),
            ('u1f450_1f3fe.png', [u'\U0001f450\U0001f3fe']),
            ('u1f450_1f3ff.png', [u'\U0001f450\U0001f3ff']),
            ]),

        (None, [
            ('u1f64c.png', [u'\U0001f64c']),
            ('u1f64c_1f3fb.png', [u'\U0001f64c\U0001f3fb']),
            ('u1f64c_1f3fc.png', [u'\U0001f64c\U0001f3fc']),
            ('u1f64c_1f3fd.png', [u'\U0001f64c\U0001f3fd']),
            ('u1f64c_1f3fe.png', [u'\U0001f64c\U0001f3fe']),
            ('u1f64c_1f3ff.png', [u'\U0001f64c\U0001f3ff']),
            ]),

        (None, [
            ('u1f64f.png', [u'\U0001f64f']),
            ('u1f64f_1f3fb.png', [u'\U0001f64f\U0001f3fb']),
            ('u1f64f_1f3fc.png', [u'\U0001f64f\U0001f3fc']),
            ('u1f64f_1f3fd.png', [u'\U0001f64f\U0001f3fd']),
            ('u1f64f_1f3fe.png', [u'\U0001f64f\U0001f3fe']),
            ('u1f64f_1f3ff.png', [u'\U0001f64f\U0001f3ff']),
            ]),

        (None, [
            ('u1f91d.png', [u'\U0001f91d']),
            ('u1f91d_1f3fb.png', [u'\U0001f91d\U0001f3fb']),
            ('u1f91d_1f3fc.png', [u'\U0001f91d\U0001f3fc']),
            ('u1f91d_1f3fd.png', [u'\U0001f91d\U0001f3fd']),
            ('u1f91d_1f3fe.png', [u'\U0001f91d\U0001f3fe']),
            ('u1f91d_1f3ff.png', [u'\U0001f91d\U0001f3ff']),
            ]),

        (None, [
            ('u1f485.png', [u'\U0001f485']),
            ('u1f485_1f3fb.png', [u'\U0001f485\U0001f3fb']),
            ('u1f485_1f3fc.png', [u'\U0001f485\U0001f3fc']),
            ('u1f485_1f3fd.png', [u'\U0001f485\U0001f3fd']),
            ('u1f485_1f3fe.png', [u'\U0001f485\U0001f3fe']),
            ('u1f485_1f3ff.png', [u'\U0001f485\U0001f3ff']),
            ]),

        (None, [
            ('u1f442.png', [u'\U0001f442']),
            ('u1f442_1f3fb.png', [u'\U0001f442\U0001f3fb']),
            ('u1f442_1f3fc.png', [u'\U0001f442\U0001f3fc']),
            ('u1f442_1f3fd.png', [u'\U0001f442\U0001f3fd']),
            ('u1f442_1f3fe.png', [u'\U0001f442\U0001f3fe']),
            ('u1f442_1f3ff.png', [u'\U0001f442\U0001f3ff']),
            ]),

        (None, [
            ('u1f443.png', [u'\U0001f443']),
            ('u1f443_1f3fb.png', [u'\U0001f443\U0001f3fb']),
            ('u1f443_1f3fc.png', [u'\U0001f443\U0001f3fc']),
            ('u1f443_1f3fd.png', [u'\U0001f443\U0001f3fd']),
            ('u1f443_1f3fe.png', [u'\U0001f443\U0001f3fe']),
            ('u1f443_1f3ff.png', [u'\U0001f443\U0001f3ff']),
            ]),

        ('u1f463.png', [u'\U0001f463']),
        ('u1f440.png', [u'\U0001f440']),
        ('u1f441.png', [u'\U0001f441']),
        ('u1f441_200d_1f5e8.png', [u'\U0001f441\u200d\U0001f5e8']),
        ('u1f445.png', [u'\U0001f445']),
        ('u1f444.png', [u'\U0001f444']),

        # subgroup: emotion
        ('u1f48b.png', [u'\U0001f48b']),
        ('u1f498.png', [u'\U0001f498']),
        ('u2764.png', [u'\u2764']),
        ('u1f493.png', [u'\U0001f493']),
        ('u1f494.png', [u'\U0001f494', '</3']),
        ('u1f495.png', [u'\U0001f495']),
        ('u1f496.png', [u'\U0001f496']),
        ('u1f497.png', [u'\U0001f497']),
        ('u1f499.png', [u'\U0001f499']),
        ('u1f49a.png', [u'\U0001f49a']),
        ('u1f49b.png', [u'\U0001f49b']),
        ('u1f49c.png', [u'\U0001f49c']),
        ('u1f5a4.png', [u'\U0001f5a4']),
        ('u1f49d.png', [u'\U0001f49d']),
        ('u1f49e.png', [u'\U0001f49e']),
        ('u1f49f.png', [u'\U0001f49f']),
        ('u2763.png', [u'\u2763']),
        ('u1f48c.png', [u'\U0001f48c']),
        ('u1f4a4.png', [u'\U0001f4a4']),
        ('u1f4a2.png', [u'\U0001f4a2']),
        ('u1f4a3.png', [u'\U0001f4a3']),
        ('u1f4a5.png', [u'\U0001f4a5']),
        ('u1f4a6.png', [u'\U0001f4a6']),
        ('u1f4a8.png', [u'\U0001f4a8']),
        ('u1f4ab.png', [u'\U0001f4ab']),
        ('u1f4ac.png', [u'\U0001f4ac']),
        ('u1f5e8.png', [u'\U0001f5e8']),
        ('u1f5ef.png', [u'\U0001f5ef']),
        ('u1f4ad.png', [u'\U0001f4ad']),
        ('u1f573.png', [u'\U0001f573']),

        # subgroup: clothing
        ('u1f453.png', [u'\U0001f453']),
        ('u1f576.png', [u'\U0001f576']),
        ('u1f454.png', [u'\U0001f454']),
        ('u1f455.png', [u'\U0001f455']),
        ('u1f456.png', [u'\U0001f456']),
        ('u1f457.png', [u'\U0001f457']),
        ('u1f458.png', [u'\U0001f458']),
        ('u1f459.png', [u'\U0001f459']),
        ('u1f45a.png', [u'\U0001f45a']),
        ('u1f45b.png', [u'\U0001f45b']),
        ('u1f45c.png', [u'\U0001f45c']),
        ('u1f45d.png', [u'\U0001f45d']),
        ('u1f6cd.png', [u'\U0001f6cd']),
        ('u1f392.png', [u'\U0001f392']),
        ('u1f45e.png', [u'\U0001f45e']),
        ('u1f45f.png', [u'\U0001f45f']),
        ('u1f460.png', [u'\U0001f460']),
        ('u1f461.png', [u'\U0001f461']),
        ('u1f462.png', [u'\U0001f462']),
        ('u1f451.png', [u'\U0001f451']),
        ('u1f452.png', [u'\U0001f452']),
        ('u1f3a9.png', [u'\U0001f3a9']),
        ('u1f393.png', [u'\U0001f393']),
        ('u26d1.png', [u'\u26d1']),
        ('u1f4ff.png', [u'\U0001f4ff']),
        ('u1f484.png', [u'\U0001f484']),
        ('u1f48d.png', [u'\U0001f48d']),
        ('u1f48e.png', [u'\U0001f48e']),

        ]),

    ('Animals & Nature', [
        # group: Animals & Nature
        ('u1f43c.png', None),  # Category image

        # subgroup: animal-mammal
        ('u1f435.png', [u'\U0001f435']),
        ('u1f412.png', [u'\U0001f412']),
        ('u1f98d.png', [u'\U0001f98d']),
        ('u1f436.png', [u'\U0001f436']),
        ('u1f415.png', [u'\U0001f415']),
        ('u1f429.png', [u'\U0001f429']),
        ('u1f43a.png', [u'\U0001f43a']),
        ('u1f98a.png', [u'\U0001f98a']),
        ('u1f431.png', [u'\U0001f431', '=^.^=']),
        ('u1f408.png', [u'\U0001f408']),
        ('u1f981.png', [u'\U0001f981', ':3', '>:3']),
        ('u1f42f.png', [u'\U0001f42f']),
        ('u1f405.png', [u'\U0001f405']),
        ('u1f406.png', [u'\U0001f406']),
        ('u1f434.png', [u'\U0001f434']),
        ('u1f40e.png', [u'\U0001f40e']),
        ('u1f984.png', [u'\U0001f984']),
        ('u1f98c.png', [u'\U0001f98c']),
        ('u1f42e.png', [u'\U0001f42e']),
        ('u1f402.png', [u'\U0001f402']),
        ('u1f403.png', [u'\U0001f403']),
        ('u1f404.png', [u'\U0001f404']),
        ('u1f437.png', [u'\U0001f437']),
        ('u1f416.png', [u'\U0001f416']),
        ('u1f417.png', [u'\U0001f417']),
        ('u1f43d.png', [u'\U0001f43d']),
        ('u1f40f.png', [u'\U0001f40f']),
        ('u1f411.png', [u'\U0001f411']),
        ('u1f410.png', [u'\U0001f410']),
        ('u1f42a.png', [u'\U0001f42a']),
        ('u1f42b.png', [u'\U0001f42b']),
        ('u1f418.png', [u'\U0001f418']),
        ('u1f98f.png', [u'\U0001f98f']),
        ('u1f42d.png', [u'\U0001f42d']),
        ('u1f401.png', [u'\U0001f401']),
        ('u1f400.png', [u'\U0001f400']),
        ('u1f439.png', [u'\U0001f439']),
        ('u1f430.png', [u'\U0001f430']),
        ('u1f407.png', [u'\U0001f407']),
        ('u1f43f.png', [u'\U0001f43f']),
        ('u1f987.png', [u'\U0001f987']),
        ('u1f43b.png', [u'\U0001f43b']),
        ('u1f428.png', [u'\U0001f428']),
        ('u1f43c.png', [u'\U0001f43c']),
        ('u1f43e.png', [u'\U0001f43e']),

        # subgroup: animal-bird
        ('u1f983.png', [u'\U0001f983']),
        ('u1f414.png', [u'\U0001f414']),
        ('u1f413.png', [u'\U0001f413']),
        ('u1f423.png', [u'\U0001f423']),
        ('u1f424.png', [u'\U0001f424']),
        ('u1f425.png', [u'\U0001f425']),
        ('u1f426.png', [u'\U0001f426']),
        ('u1f427.png', [u'\U0001f427']),
        ('u1f54a.png', [u'\U0001f54a']),
        ('u1f985.png', [u'\U0001f985']),
        ('u1f986.png', [u'\U0001f986']),
        ('u1f989.png', [u'\U0001f989']),

        # subgroup: animal-amphibian
        ('u1f438.png', [u'\U0001f438']),

        # subgroup: animal-reptile
        ('u1f40a.png', [u'\U0001f40a']),
        ('u1f422.png', [u'\U0001f422']),
        ('u1f98e.png', [u'\U0001f98e']),
        ('u1f40d.png', [u'\U0001f40d']),
        ('u1f432.png', [u'\U0001f432']),
        ('u1f409.png', [u'\U0001f409']),

        # subgroup: animal-marine
        ('u1f433.png', [u'\U0001f433']),

        ('u1f40b.png', [u'\U0001f40b']),
        ('u1f42c.png', [u'\U0001f42c']),
        ('u1f41f.png', [u'\U0001f41f']),
        ('u1f420.png', [u'\U0001f420']),
        ('u1f421.png', [u'\U0001f421']),
        ('u1f988.png', [u'\U0001f988']),
        ('u1f419.png', [u'\U0001f419']),
        ('u1f41a.png', [u'\U0001f41a']),
        ('u1f980.png', [u'\U0001f980']),
        ('u1f990.png', [u'\U0001f990']),
        ('u1f991.png', [u'\U0001f991']),

        # subgroup: animal-bug
        ('u1f40c.png', [u'\U0001f40c']),
        ('u1f98b.png', [u'\U0001f98b']),
        ('u1f41b.png', [u'\U0001f41b']),
        ('u1f41c.png', [u'\U0001f41c']),
        ('u1f41d.png', [u'\U0001f41d']),
        ('u1f41e.png', [u'\U0001f41e']),
        ('u1f577.png', [u'\U0001f577']),
        ('u1f578.png', [u'\U0001f578']),
        ('u1f982.png', [u'\U0001f982']),

        # subgroup: plant-flower
        ('u1f490.png', [u'\U0001f490']),
        ('u1f338.png', [u'\U0001f338']),
        ('u1f4ae.png', [u'\U0001f4ae']),
        ('u1f3f5.png', [u'\U0001f3f5']),
        ('u1f339.png', [u'\U0001f339']),
        ('u1f940.png', [u'\U0001f940']),
        ('u1f33a.png', [u'\U0001f33a']),
        ('u1f33b.png', [u'\U0001f33b']),
        ('u1f33c.png', [u'\U0001f33c']),
        ('u1f337.png', [u'\U0001f337']),

        # subgroup: plant-other
        ('u1f331.png', [u'\U0001f331']),
        ('u1f332.png', [u'\U0001f332']),
        ('u1f333.png', [u'\U0001f333']),
        ('u1f334.png', [u'\U0001f334']),
        ('u1f335.png', [u'\U0001f335']),
        ('u1f33e.png', [u'\U0001f33e']),
        ('u1f33f.png', [u'\U0001f33f']),
        ('u2618.png', [u'\u2618']),
        ('u1f340.png', [u'\U0001f340']),
        ('u1f341.png', [u'\U0001f341']),
        ('u1f342.png', [u'\U0001f342']),
        ('u1f343.png', [u'\U0001f343']),

        ]),

    ('Food & Drink', [
        # group: Food & Drink
        ('u1f349.png', None),  # Category image

        # subgroup: food-fruit
        ('u1f347.png', [u'\U0001f347']),
        ('u1f348.png', [u'\U0001f348']),
        ('u1f349.png', [u'\U0001f349']),
        ('u1f34a.png', [u'\U0001f34a']),
        ('u1f34b.png', [u'\U0001f34b']),
        ('u1f34c.png', [u'\U0001f34c']),
        ('u1f34d.png', [u'\U0001f34d']),
        ('u1f34e.png', [u'\U0001f34e']),
        ('u1f34f.png', [u'\U0001f34f']),
        ('u1f350.png', [u'\U0001f350']),
        ('u1f351.png', [u'\U0001f351']),
        ('u1f352.png', [u'\U0001f352']),
        ('u1f353.png', [u'\U0001f353']),
        ('u1f95d.png', [u'\U0001f95d']),
        ('u1f345.png', [u'\U0001f345']),

        # subgroup: food-vegetable
        ('u1f951.png', [u'\U0001f951']),
        ('u1f346.png', [u'\U0001f346']),
        ('u1f954.png', [u'\U0001f954']),
        ('u1f955.png', [u'\U0001f955']),
        ('u1f33d.png', [u'\U0001f33d']),
        ('u1f336.png', [u'\U0001f336']),
        ('u1f952.png', [u'\U0001f952']),
        ('u1f344.png', [u'\U0001f344']),
        ('u1f95c.png', [u'\U0001f95c']),
        ('u1f330.png', [u'\U0001f330']),

        # subgroup: food-prepared
        ('u1f35e.png', [u'\U0001f35e']),
        ('u1f950.png', [u'\U0001f950']),
        ('u1f956.png', [u'\U0001f956']),
        ('u1f95e.png', [u'\U0001f95e']),
        ('u1f9c0.png', [u'\U0001f9c0']),
        ('u1f356.png', [u'\U0001f356']),
        ('u1f357.png', [u'\U0001f357']),
        ('u1f953.png', [u'\U0001f953']),
        ('u1f354.png', [u'\U0001f354']),
        ('u1f35f.png', [u'\U0001f35f']),
        ('u1f355.png', [u'\U0001f355']),
        ('u1f32d.png', [u'\U0001f32d']),
        ('u1f32e.png', [u'\U0001f32e']),
        ('u1f32f.png', [u'\U0001f32f']),
        ('u1f959.png', [u'\U0001f959']),
        ('u1f95a.png', [u'\U0001f95a']),
        ('u1f373.png', [u'\U0001f373']),
        ('u1f958.png', [u'\U0001f958']),
        ('u1f372.png', [u'\U0001f372']),
        ('u1f957.png', [u'\U0001f957']),
        ('u1f37f.png', [u'\U0001f37f']),

        # subgroup: food-asian
        ('u1f371.png', [u'\U0001f371']),
        ('u1f358.png', [u'\U0001f358']),
        ('u1f359.png', [u'\U0001f359']),
        ('u1f35a.png', [u'\U0001f35a']),
        ('u1f35b.png', [u'\U0001f35b']),
        ('u1f35c.png', [u'\U0001f35c']),
        ('u1f35d.png', [u'\U0001f35d']),
        ('u1f360.png', [u'\U0001f360']),
        ('u1f362.png', [u'\U0001f362']),
        ('u1f363.png', [u'\U0001f363']),
        ('u1f364.png', [u'\U0001f364']),
        ('u1f365.png', [u'\U0001f365']),
        ('u1f361.png', [u'\U0001f361']),

        # subgroup: food-sweet
        ('u1f366.png', [u'\U0001f366']),
        ('u1f367.png', [u'\U0001f367']),
        ('u1f368.png', [u'\U0001f368']),
        ('u1f369.png', [u'\U0001f369']),
        ('u1f36a.png', [u'\U0001f36a']),
        ('u1f382.png', [u'\U0001f382']),
        ('u1f370.png', [u'\U0001f370']),
        ('u1f36b.png', [u'\U0001f36b']),
        ('u1f36c.png', [u'\U0001f36c']),
        ('u1f36d.png', [u'\U0001f36d']),
        ('u1f36e.png', [u'\U0001f36e']),
        ('u1f36f.png', [u'\U0001f36f']),

        # subgroup: drink
        ('u1f37c.png', [u'\U0001f37c']),
        ('u1f95b.png', [u'\U0001f95b']),
        ('u2615.png', [u'\u2615']),
        ('u1f375.png', [u'\U0001f375']),
        ('u1f376.png', [u'\U0001f376']),
        ('u1f37e.png', [u'\U0001f37e']),
        ('u1f377.png', [u'\U0001f377']),
        ('u1f378.png', [u'\U0001f378']),
        ('u1f379.png', [u'\U0001f379']),
        ('u1f37a.png', [u'\U0001f37a']),
        ('u1f37b.png', [u'\U0001f37b']),
        ('u1f942.png', [u'\U0001f942']),
        ('u1f943.png', [u'\U0001f943']),

        # subgroup: dishware
        ('u1f37d.png', [u'\U0001f37d']),
        ('u1f374.png', [u'\U0001f374']),
        ('u1f944.png', [u'\U0001f944']),
        ('u1f52a.png', [u'\U0001f52a']),
        ('u1f3fa.png', [u'\U0001f3fa']),

        ]),

    ('Travel & Places', [
        # group: Travel & Places
        ('u2708.png', None),  # Category image

        # subgroup: place-map
        ('u1f30d.png', [u'\U0001f30d']),
        ('u1f30e.png', [u'\U0001f30e']),
        ('u1f30f.png', [u'\U0001f30f']),
        ('u1f310.png', [u'\U0001f310']),
        ('u1f5fa.png', [u'\U0001f5fa']),
        ('u1f5fe.png', [u'\U0001f5fe']),

        # subgroup: place-geographic
        ('u1f3d4.png', [u'\U0001f3d4']),
        ('u26f0.png', [u'\u26f0']),
        ('u1f30b.png', [u'\U0001f30b']),
        ('u1f5fb.png', [u'\U0001f5fb']),
        ('u1f3d5.png', [u'\U0001f3d5']),
        ('u1f3d6.png', [u'\U0001f3d6']),
        ('u1f3dc.png', [u'\U0001f3dc']),
        ('u1f3dd.png', [u'\U0001f3dd']),
        ('u1f3de.png', [u'\U0001f3de']),

        # subgroup: place-building
        ('u1f3df.png', [u'\U0001f3df']),
        ('u1f3db.png', [u'\U0001f3db']),
        ('u1f3d7.png', [u'\U0001f3d7']),
        ('u1f3d8.png', [u'\U0001f3d8']),
        ('u1f3d9.png', [u'\U0001f3d9']),
        ('u1f3da.png', [u'\U0001f3da']),
        ('u1f3e0.png', [u'\U0001f3e0']),
        ('u1f3e1.png', [u'\U0001f3e1']),
        ('u1f3e2.png', [u'\U0001f3e2']),
        ('u1f3e3.png', [u'\U0001f3e3']),
        ('u1f3e4.png', [u'\U0001f3e4']),
        ('u1f3e5.png', [u'\U0001f3e5']),
        ('u1f3e6.png', [u'\U0001f3e6']),
        ('u1f3e8.png', [u'\U0001f3e8']),
        ('u1f3e9.png', [u'\U0001f3e9']),
        ('u1f3ea.png', [u'\U0001f3ea']),
        ('u1f3eb.png', [u'\U0001f3eb']),
        ('u1f3ec.png', [u'\U0001f3ec']),
        ('u1f3ed.png', [u'\U0001f3ed']),
        ('u1f3ef.png', [u'\U0001f3ef']),
        ('u1f3f0.png', [u'\U0001f3f0']),
        ('u1f492.png', [u'\U0001f492']),
        ('u1f5fc.png', [u'\U0001f5fc']),
        ('u1f5fd.png', [u'\U0001f5fd']),

        # subgroup: place-religious
        ('u26ea.png', [u'\u26ea']),
        ('u1f54c.png', [u'\U0001f54c']),
        ('u1f54d.png', [u'\U0001f54d']),
        ('u26e9.png', [u'\u26e9']),
        ('u1f54b.png', [u'\U0001f54b']),

        # subgroup: place-other
        ('u26f2.png', [u'\u26f2']),
        ('u26fa.png', [u'\u26fa']),
        ('u1f301.png', [u'\U0001f301']),
        ('u1f303.png', [u'\U0001f303']),
        ('u1f304.png', [u'\U0001f304']),
        ('u1f305.png', [u'\U0001f305']),
        ('u1f306.png', [u'\U0001f306']),
        ('u1f307.png', [u'\U0001f307']),
        ('u1f309.png', [u'\U0001f309']),
        ('u2668.png', [u'\u2668']),
        ('u1f30c.png', [u'\U0001f30c']),
        ('u1f3a0.png', [u'\U0001f3a0']),
        ('u1f3a1.png', [u'\U0001f3a1']),
        ('u1f3a2.png', [u'\U0001f3a2']),
        ('u1f488.png', [u'\U0001f488']),
        ('u1f3aa.png', [u'\U0001f3aa']),
        ('u1f3ad.png', [u'\U0001f3ad']),
        ('u1f5bc.png', [u'\U0001f5bc']),
        ('u1f3a8.png', [u'\U0001f3a8']),
        ('u1f3b0.png', [u'\U0001f3b0']),


        # subgroup: transport-ground
        ('u1f682.png', [u'\U0001f682']),
        ('u1f683.png', [u'\U0001f683']),
        ('u1f684.png', [u'\U0001f684']),
        ('u1f685.png', [u'\U0001f685']),
        ('u1f686.png', [u'\U0001f686']),
        ('u1f687.png', [u'\U0001f687']),
        ('u1f688.png', [u'\U0001f688']),
        ('u1f689.png', [u'\U0001f689']),
        ('u1f68a.png', [u'\U0001f68a']),
        ('u1f69d.png', [u'\U0001f69d']),
        ('u1f69e.png', [u'\U0001f69e']),
        ('u1f68b.png', [u'\U0001f68b']),
        ('u1f68c.png', [u'\U0001f68c']),
        ('u1f68d.png', [u'\U0001f68d']),
        ('u1f68e.png', [u'\U0001f68e']),
        ('u1f690.png', [u'\U0001f690']),
        ('u1f691.png', [u'\U0001f691']),
        ('u1f692.png', [u'\U0001f692']),
        ('u1f693.png', [u'\U0001f693']),
        ('u1f694.png', [u'\U0001f694']),
        ('u1f695.png', [u'\U0001f695']),
        ('u1f696.png', [u'\U0001f696']),
        ('u1f697.png', [u'\U0001f697']),
        ('u1f698.png', [u'\U0001f698']),
        ('u1f699.png', [u'\U0001f699']),
        ('u1f69a.png', [u'\U0001f69a']),
        ('u1f69b.png', [u'\U0001f69b']),
        ('u1f69c.png', [u'\U0001f69c']),
        ('u1f6b2.png', [u'\U0001f6b2']),
        ('u1f6f4.png', [u'\U0001f6f4']),
        ('u1f6f5.png', [u'\U0001f6f5']),
        ('u1f68f.png', [u'\U0001f68f']),
        ('u1f6e3.png', [u'\U0001f6e3']),
        ('u1f6e4.png', [u'\U0001f6e4']),
        ('u26fd.png', [u'\u26fd']),
        ('u1f6a8.png', [u'\U0001f6a8']),
        ('u1f6a5.png', [u'\U0001f6a5']),
        ('u1f6a6.png', [u'\U0001f6a6']),
        ('u1f6a7.png', [u'\U0001f6a7']),
        ('u1f6d1.png', [u'\U0001f6d1']),

        # subgroup: transport-water
        ('u2693.png', [u'\u2693']),
        ('u26f5.png', [u'\u26f5']),
        ('u1f6f6.png', [u'\U0001f6f6']),
        ('u1f6a4.png', [u'\U0001f6a4']),
        ('u1f6f3.png', [u'\U0001f6f3']),
        ('u26f4.png', [u'\u26f4']),
        ('u1f6e5.png', [u'\U0001f6e5']),
        ('u1f6a2.png', [u'\U0001f6a2']),

        # subgroup: transport-air
        ('u2708.png', [u'\u2708']),
        ('u1f6e9.png', [u'\U0001f6e9']),
        ('u1f6eb.png', [u'\U0001f6eb']),
        ('u1f6ec.png', [u'\U0001f6ec']),
        ('u1f4ba.png', [u'\U0001f4ba']),
        ('u1f681.png', [u'\U0001f681']),
        ('u1f69f.png', [u'\U0001f69f']),
        ('u1f6a0.png', [u'\U0001f6a0']),
        ('u1f6a1.png', [u'\U0001f6a1']),
        ('u1f6f0.png', [u'\U0001f6f0']),
        ('u1f680.png', [u'\U0001f680']),

        # subgroup: hotel
        ('u1f6ce.png', [u'\U0001f6ce']),
        ('u1f6aa.png', [u'\U0001f6aa']),
        ('u1f6cf.png', [u'\U0001f6cf']),
        ('u1f6cb.png', [u'\U0001f6cb']),
        ('u1f6bd.png', [u'\U0001f6bd']),
        ('u1f6bf.png', [u'\U0001f6bf']),
        ('u1f6c1.png', [u'\U0001f6c1']),


        # subgroup: time
        ('u231b.png', [u'\u231b']),
        ('u23f3.png', [u'\u23f3']),
        ('u231a.png', [u'\u231a']),
        ('u23f0.png', [u'\u23f0']),
        ('u23f1.png', [u'\u23f1']),
        ('u23f2.png', [u'\u23f2']),
        ('u1f570.png', [u'\U0001f570']),

        (None, [
            ('u1f55b.png', [u'\U0001f55b']),
            ('u1f567.png', [u'\U0001f567']),
            ('u1f550.png', [u'\U0001f550']),
            ('u1f55c.png', [u'\U0001f55c']),
            ('u1f551.png', [u'\U0001f551']),
            ('u1f55d.png', [u'\U0001f55d']),
            ('u1f552.png', [u'\U0001f552']),
            ('u1f55e.png', [u'\U0001f55e']),
            ('u1f553.png', [u'\U0001f553']),
            ('u1f55f.png', [u'\U0001f55f']),
            ('u1f554.png', [u'\U0001f554']),
            ('u1f560.png', [u'\U0001f560']),
            ('u1f555.png', [u'\U0001f555']),
            ('u1f561.png', [u'\U0001f561']),
            ('u1f556.png', [u'\U0001f556']),
            ('u1f562.png', [u'\U0001f562']),
            ('u1f557.png', [u'\U0001f557']),
            ('u1f563.png', [u'\U0001f563']),
            ('u1f558.png', [u'\U0001f558']),
            ('u1f564.png', [u'\U0001f564']),
            ('u1f559.png', [u'\U0001f559']),
            ('u1f565.png', [u'\U0001f565']),
            ('u1f55a.png', [u'\U0001f55a']),
            ('u1f566.png', [u'\U0001f566']),
            ]),

        # subgroup: sky & weather
        ('u1f311.png', [u'\U0001f311']),
        ('u1f312.png', [u'\U0001f312']),
        ('u1f313.png', [u'\U0001f313']),
        ('u1f314.png', [u'\U0001f314']),
        ('u1f315.png', [u'\U0001f315']),
        ('u1f316.png', [u'\U0001f316']),
        ('u1f317.png', [u'\U0001f317']),
        ('u1f318.png', [u'\U0001f318']),
        ('u1f319.png', [u'\U0001f319']),
        ('u1f31a.png', [u'\U0001f31a']),
        ('u1f31b.png', [u'\U0001f31b']),
        ('u1f31c.png', [u'\U0001f31c']),
        ('u1f321.png', [u'\U0001f321']),
        ('u2600.png', [u'\u2600']),
        ('u1f31d.png', [u'\U0001f31d']),
        ('u1f31e.png', [u'\U0001f31e']),
        ('u2b50.png', [u'\u2b50']),
        ('u1f31f.png', [u'\U0001f31f']),
        ('u1f320.png', [u'\U0001f320']),
        ('u2601.png', [u'\u2601']),
        ('u26c5.png', [u'\u26c5']),
        ('u26c8.png', [u'\u26c8']),
        ('u1f324.png', [u'\U0001f324']),
        ('u1f325.png', [u'\U0001f325']),
        ('u1f326.png', [u'\U0001f326']),
        ('u1f327.png', [u'\U0001f327']),
        ('u1f328.png', [u'\U0001f328']),
        ('u1f329.png', [u'\U0001f329']),
        ('u1f32a.png', [u'\U0001f32a']),
        ('u1f32b.png', [u'\U0001f32b']),
        ('u1f32c.png', [u'\U0001f32c']),
        ('u1f300.png', [u'\U0001f300']),
        ('u1f308.png', [u'\U0001f308']),
        ('u1f302.png', [u'\U0001f302']),
        ('u2602.png', [u'\u2602']),
        ('u2614.png', [u'\u2614']),
        ('u26f1.png', [u'\u26f1']),
        ('u26a1.png', [u'\u26a1']),
        ('u2744.png', [u'\u2744']),
        ('u2603.png', [u'\u2603']),
        ('u26c4.png', [u'\u26c4']),
        ('u2604.png', [u'\u2604']),
        ('u1f525.png', [u'\U0001f525']),
        ('u1f4a7.png', [u'\U0001f4a7']),
        ('u1f30a.png', [u'\U0001f30a']),

        ]),

    ('Activity', [
        # group: Activities
        ('u26bd.png', None),  # Category image

        # subgroup: event
        ('u1f383.png', [u'\U0001f383']),
        ('u1f384.png', [u'\U0001f384']),
        ('u1f386.png', [u'\U0001f386']),
        ('u1f387.png', [u'\U0001f387']),
        ('u2728.png', [u'\u2728']),
        ('u1f388.png', [u'\U0001f388']),
        ('u1f389.png', [u'\U0001f389']),
        ('u1f38a.png', [u'\U0001f38a']),
        ('u1f38b.png', [u'\U0001f38b']),
        ('u1f38d.png', [u'\U0001f38d']),
        ('u1f38e.png', [u'\U0001f38e']),
        ('u1f38f.png', [u'\U0001f38f']),
        ('u1f390.png', [u'\U0001f390']),
        ('u1f391.png', [u'\U0001f391']),
        ('u1f380.png', [u'\U0001f380']),
        ('u1f381.png', [u'\U0001f381']),
        ('u1f397.png', [u'\U0001f397']),
        ('u1f39f.png', [u'\U0001f39f']),
        ('u1f3ab.png', [u'\U0001f3ab']),

        # subgroup: award-medal
        ('u1f396.png', [u'\U0001f396']),
        ('u1f3c6.png', [u'\U0001f3c6']),
        ('u1f3c5.png', [u'\U0001f3c5']),
        ('u1f947.png', [u'\U0001f947']),
        ('u1f948.png', [u'\U0001f948']),
        ('u1f949.png', [u'\U0001f949']),

        # subgroup: sport
        ('u26bd.png', [u'\u26bd']),
        ('u26be.png', [u'\u26be']),
        ('u1f3c0.png', [u'\U0001f3c0']),
        ('u1f3d0.png', [u'\U0001f3d0']),
        ('u1f3c8.png', [u'\U0001f3c8']),
        ('u1f3c9.png', [u'\U0001f3c9']),
        ('u1f3be.png', [u'\U0001f3be']),
        ('u1f3b1.png', [u'\U0001f3b1']),
        ('u1f3b3.png', [u'\U0001f3b3']),
        ('u1f3cf.png', [u'\U0001f3cf']),
        ('u1f3d1.png', [u'\U0001f3d1']),
        ('u1f3d2.png', [u'\U0001f3d2']),
        ('u1f3d3.png', [u'\U0001f3d3']),
        ('u1f3f8.png', [u'\U0001f3f8']),
        ('u1f94a.png', [u'\U0001f94a']),
        ('u1f94b.png', [u'\U0001f94b']),
        ('u1f945.png', [u'\U0001f945']),
        ('u1f3af.png', [u'\U0001f3af']),
        ('u26f3.png', [u'\u26f3']),
        ('u26f8.png', [u'\u26f8']),
        ('u1f3a3.png', [u'\U0001f3a3']),
        ('u1f3bd.png', [u'\U0001f3bd']),
        ('u1f3bf.png', [u'\U0001f3bf']),

        # subgroup: game
        ('u1f3ae.png', [u'\U0001f3ae']),
        ('u1f579.png', [u'\U0001f579']),
        ('u1f3b2.png', [u'\U0001f3b2']),
        ('u2660.png', [u'\u2660']),
        ('u2665.png', [u'\u2665']),
        ('u2666.png', [u'\u2666']),
        ('u2663.png', [u'\u2663']),
        ('u1f0cf.png', [u'\U0001f0cf']),
        ('u1f004.png', [u'\U0001f004']),
        ('u1f3b4.png', [u'\U0001f3b4']),

        ]),

    ('Objects', [
        # group: Objects
        ('u1f3a7.png', None),  # Category image

        # subgroup: sound
        ('u1f507.png', [u'\U0001f507']),
        ('u1f508.png', [u'\U0001f508']),
        ('u1f509.png', [u'\U0001f509']),
        ('u1f50a.png', [u'\U0001f50a']),
        ('u1f4e2.png', [u'\U0001f4e2']),
        ('u1f4e3.png', [u'\U0001f4e3']),
        ('u1f4ef.png', [u'\U0001f4ef']),
        ('u1f514.png', [u'\U0001f514']),
        ('u1f515.png', [u'\U0001f515']),

        # subgroup: music
        ('u1f3bc.png', [u'\U0001f3bc']),
        ('u1f3b5.png', [u'\U0001f3b5']),
        ('u1f3b6.png', [u'\U0001f3b6']),
        ('u1f399.png', [u'\U0001f399']),
        ('u1f39a.png', [u'\U0001f39a']),
        ('u1f39b.png', [u'\U0001f39b']),
        ('u1f3a4.png', [u'\U0001f3a4']),
        ('u1f3a7.png', [u'\U0001f3a7']),
        ('u1f4fb.png', [u'\U0001f4fb']),

        # subgroup: musical-instrument
        ('u1f3b7.png', [u'\U0001f3b7']),
        ('u1f3b8.png', [u'\U0001f3b8']),
        ('u1f3b9.png', [u'\U0001f3b9']),
        ('u1f3ba.png', [u'\U0001f3ba']),
        ('u1f3bb.png', [u'\U0001f3bb']),
        ('u1f941.png', [u'\U0001f941']),

        # subgroup: phone
        ('u1f4f1.png', [u'\U0001f4f1']),
        ('u1f4f2.png', [u'\U0001f4f2']),
        ('u260e.png', [u'\u260e']),
        ('u1f4de.png', [u'\U0001f4de']),
        ('u1f4df.png', [u'\U0001f4df']),
        ('u1f4e0.png', [u'\U0001f4e0']),

        # subgroup: computer
        ('u1f50b.png', [u'\U0001f50b']),
        ('u1f50c.png', [u'\U0001f50c']),
        ('u1f4bb.png', [u'\U0001f4bb']),
        ('u1f5a5.png', [u'\U0001f5a5']),
        ('u1f5a8.png', [u'\U0001f5a8']),
        ('u2328.png', [u'\u2328']),
        ('u1f5b1.png', [u'\U0001f5b1']),
        ('u1f5b2.png', [u'\U0001f5b2']),
        ('u1f4bd.png', [u'\U0001f4bd']),
        ('u1f4be.png', [u'\U0001f4be']),
        ('u1f4bf.png', [u'\U0001f4bf']),
        ('u1f4c0.png', [u'\U0001f4c0']),

        # subgroup: light & video
        ('u1f3a5.png', [u'\U0001f3a5']),
        ('u1f39e.png', [u'\U0001f39e']),
        ('u1f4fd.png', [u'\U0001f4fd']),
        ('u1f3ac.png', [u'\U0001f3ac']),
        ('u1f4fa.png', [u'\U0001f4fa']),
        ('u1f4f7.png', [u'\U0001f4f7']),
        ('u1f4f8.png', [u'\U0001f4f8']),
        ('u1f4f9.png', [u'\U0001f4f9']),
        ('u1f4fc.png', [u'\U0001f4fc']),
        ('u1f50d.png', [u'\U0001f50d']),
        ('u1f50e.png', [u'\U0001f50e']),
        ('u1f52c.png', [u'\U0001f52c']),
        ('u1f52d.png', [u'\U0001f52d']),
        ('u1f4e1.png', [u'\U0001f4e1']),
        ('u1f56f.png', [u'\U0001f56f']),
        ('u1f4a1.png', [u'\U0001f4a1']),
        ('u1f526.png', [u'\U0001f526']),
        ('u1f3ee.png', [u'\U0001f3ee']),

        # subgroup: book-paper
        ('u1f4d4.png', [u'\U0001f4d4']),
        ('u1f4d5.png', [u'\U0001f4d5']),
        ('u1f4d6.png', [u'\U0001f4d6']),
        ('u1f4d7.png', [u'\U0001f4d7']),
        ('u1f4d8.png', [u'\U0001f4d8']),
        ('u1f4d9.png', [u'\U0001f4d9']),
        ('u1f4da.png', [u'\U0001f4da']),
        ('u1f4d3.png', [u'\U0001f4d3']),
        ('u1f4d2.png', [u'\U0001f4d2']),
        ('u1f4c3.png', [u'\U0001f4c3']),
        ('u1f4dc.png', [u'\U0001f4dc']),
        ('u1f4c4.png', [u'\U0001f4c4']),
        ('u1f4f0.png', [u'\U0001f4f0']),
        ('u1f5de.png', [u'\U0001f5de']),
        ('u1f4d1.png', [u'\U0001f4d1']),
        ('u1f516.png', [u'\U0001f516']),
        ('u1f3f7.png', [u'\U0001f3f7']),

        # subgroup: money
        ('u1f4b0.png', [u'\U0001f4b0']),
        ('u1f4b4.png', [u'\U0001f4b4']),
        ('u1f4b5.png', [u'\U0001f4b5']),
        ('u1f4b6.png', [u'\U0001f4b6']),
        ('u1f4b7.png', [u'\U0001f4b7']),
        ('u1f4b8.png', [u'\U0001f4b8']),
        ('u1f4b3.png', [u'\U0001f4b3']),
        ('u1f4b9.png', [u'\U0001f4b9']),
        ('u1f4b1.png', [u'\U0001f4b1']),
        ('u1f4b2.png', [u'\U0001f4b2']),

        # subgroup: mail
        ('u2709.png', [u'\u2709']),
        ('u1f4e7.png', [u'\U0001f4e7']),
        ('u1f4e8.png', [u'\U0001f4e8']),
        ('u1f4e9.png', [u'\U0001f4e9']),
        ('u1f4e4.png', [u'\U0001f4e4']),
        ('u1f4e5.png', [u'\U0001f4e5']),
        ('u1f4e6.png', [u'\U0001f4e6']),
        ('u1f4eb.png', [u'\U0001f4eb']),
        ('u1f4ea.png', [u'\U0001f4ea']),
        ('u1f4ec.png', [u'\U0001f4ec']),
        ('u1f4ed.png', [u'\U0001f4ed']),
        ('u1f4ee.png', [u'\U0001f4ee']),
        ('u1f5f3.png', [u'\U0001f5f3']),

        # subgroup: writing
        ('u270f.png', [u'\u270f']),
        ('u2712.png', [u'\u2712']),
        ('u1f58b.png', [u'\U0001f58b']),
        ('u1f58a.png', [u'\U0001f58a']),
        ('u1f58c.png', [u'\U0001f58c']),
        ('u1f58d.png', [u'\U0001f58d']),
        ('u1f4dd.png', [u'\U0001f4dd']),

        # subgroup: office
        ('u1f4bc.png', [u'\U0001f4bc']),
        ('u1f4c1.png', [u'\U0001f4c1']),
        ('u1f4c2.png', [u'\U0001f4c2']),
        ('u1f5c2.png', [u'\U0001f5c2']),
        ('u1f4c5.png', [u'\U0001f4c5']),
        ('u1f4c6.png', [u'\U0001f4c6']),
        ('u1f5d2.png', [u'\U0001f5d2']),
        ('u1f5d3.png', [u'\U0001f5d3']),
        ('u1f4c7.png', [u'\U0001f4c7']),
        ('u1f4c8.png', [u'\U0001f4c8']),
        ('u1f4c9.png', [u'\U0001f4c9']),
        ('u1f4ca.png', [u'\U0001f4ca']),
        ('u1f4cb.png', [u'\U0001f4cb']),
        ('u1f4cc.png', [u'\U0001f4cc']),
        ('u1f4cd.png', [u'\U0001f4cd']),
        ('u1f4ce.png', [u'\U0001f4ce']),
        ('u1f587.png', [u'\U0001f587']),
        ('u1f4cf.png', [u'\U0001f4cf']),
        ('u1f4d0.png', [u'\U0001f4d0']),
        ('u2702.png', [u'\u2702']),
        ('u1f5c3.png', [u'\U0001f5c3']),
        ('u1f5c4.png', [u'\U0001f5c4']),
        ('u1f5d1.png', [u'\U0001f5d1']),

        # subgroup: lock
        ('u1f512.png', [u'\U0001f512']),
        ('u1f513.png', [u'\U0001f513']),
        ('u1f50f.png', [u'\U0001f50f']),
        ('u1f510.png', [u'\U0001f510']),
        ('u1f511.png', [u'\U0001f511']),
        ('u1f5dd.png', [u'\U0001f5dd']),

        # subgroup: tool
        ('u1f528.png', [u'\U0001f528']),
        ('u26cf.png', [u'\u26cf']),
        ('u2692.png', [u'\u2692']),
        ('u1f6e0.png', [u'\U0001f6e0']),
        ('u1f5e1.png', [u'\U0001f5e1']),
        ('u2694.png', [u'\u2694']),
        ('u1f52b.png', [u'\U0001f52b']),
        ('u1f3f9.png', [u'\U0001f3f9']),
        ('u1f6e1.png', [u'\U0001f6e1']),
        ('u1f527.png', [u'\U0001f527']),
        ('u1f529.png', [u'\U0001f529']),
        ('u2699.png', [u'\u2699']),
        ('u1f5dc.png', [u'\U0001f5dc']),
        ('u2697.png', [u'\u2697']),
        ('u2696.png', [u'\u2696']),
        ('u1f517.png', [u'\U0001f517']),
        ('u26d3.png', [u'\u26d3']),

        # subgroup: medical
        ('u1f489.png', [u'\U0001f489']),
        ('u1f48a.png', [u'\U0001f48a']),

        # subgroup: other-object
        ('u1f6ac.png', [u'\U0001f6ac']),
        ('u26b0.png', [u'\u26b0']),
        ('u26b1.png', [u'\u26b1']),
        ('u1f5ff.png', [u'\U0001f5ff']),
        ('u1f6e2.png', [u'\U0001f6e2']),
        ('u1f52e.png', [u'\U0001f52e']),
        ('u1f6d2.png', [u'\U0001f6d2']),

        ]),

    ('Symbols', [
        # group: Symbols
        ('u262f.png', None),  # Category image

        # subgroup: transport-sign
        ('u1f3e7.png', [u'\U0001f3e7']),
        ('u1f6ae.png', [u'\U0001f6ae']),
        ('u1f6b0.png', [u'\U0001f6b0']),
        ('u267f.png', [u'\u267f']),
        ('u1f6b9.png', [u'\U0001f6b9']),
        ('u1f6ba.png', [u'\U0001f6ba']),
        ('u1f6bb.png', [u'\U0001f6bb']),
        ('u1f6bc.png', [u'\U0001f6bc']),
        ('u1f6be.png', [u'\U0001f6be']),
        ('u1f6c2.png', [u'\U0001f6c2']),
        ('u1f6c3.png', [u'\U0001f6c3']),
        ('u1f6c4.png', [u'\U0001f6c4']),
        ('u1f6c5.png', [u'\U0001f6c5']),

        # subgroup: warning
        ('u26a0.png', [u'\u26a0']),
        ('u1f6b8.png', [u'\U0001f6b8']),
        ('u26d4.png', [u'\u26d4']),
        ('u1f6ab.png', [u'\U0001f6ab']),
        ('u1f6b3.png', [u'\U0001f6b3']),
        ('u1f6ad.png', [u'\U0001f6ad']),
        ('u1f6af.png', [u'\U0001f6af']),
        ('u1f6b1.png', [u'\U0001f6b1']),
        ('u1f6b7.png', [u'\U0001f6b7']),
        ('u1f4f5.png', [u'\U0001f4f5']),
        ('u1f51e.png', [u'\U0001f51e']),
        ('u2622.png', [u'\u2622']),
        ('u2623.png', [u'\u2623']),

        # subgroup: arrow
        ('u2b06.png', [u'\u2b06']),
        ('u2197.png', [u'\u2197']),
        ('u27a1.png', [u'\u27a1']),
        ('u2198.png', [u'\u2198']),
        ('u2b07.png', [u'\u2b07']),
        ('u2199.png', [u'\u2199']),
        ('u2b05.png', [u'\u2b05']),
        ('u2196.png', [u'\u2196']),
        ('u2195.png', [u'\u2195']),
        ('u2194.png', [u'\u2194']),
        ('u21a9.png', [u'\u21a9']),
        ('u21aa.png', [u'\u21aa']),
        ('u2934.png', [u'\u2934']),
        ('u2935.png', [u'\u2935']),
        ('u1f503.png', [u'\U0001f503']),
        ('u1f504.png', [u'\U0001f504']),
        ('u1f519.png', [u'\U0001f519']),
        ('u1f51a.png', [u'\U0001f51a']),
        ('u1f51b.png', [u'\U0001f51b']),
        ('u1f51c.png', [u'\U0001f51c']),
        ('u1f51d.png', [u'\U0001f51d']),

        # subgroup: religion
        ('u1f6d0.png', [u'\U0001f6d0']),
        ('u269b.png', [u'\u269b']),
        ('u1f549.png', [u'\U0001f549']),
        ('u2721.png', [u'\u2721']),
        ('u2638.png', [u'\u2638']),
        ('u262f.png', [u'\u262f']),
        ('u271d.png', [u'\u271d']),
        ('u2626.png', [u'\u2626']),
        ('u262a.png', [u'\u262a']),
        ('u262e.png', [u'\u262e']),
        ('u1f54e.png', [u'\U0001f54e']),
        ('u1f52f.png', [u'\U0001f52f']),

        # subgroup: zodiac
        ('u2648.png', [u'\u2648']),
        ('u2649.png', [u'\u2649']),
        ('u264a.png', [u'\u264a']),
        ('u264b.png', [u'\u264b']),
        ('u264c.png', [u'\u264c']),
        ('u264d.png', [u'\u264d']),
        ('u264e.png', [u'\u264e']),
        ('u264f.png', [u'\u264f']),
        ('u2650.png', [u'\u2650']),
        ('u2651.png', [u'\u2651']),
        ('u2652.png', [u'\u2652']),
        ('u2653.png', [u'\u2653']),
        ('u26ce.png', [u'\u26ce']),

        # subgroup: av-symbol
        ('u1f500.png', [u'\U0001f500']),
        ('u1f501.png', [u'\U0001f501']),
        ('u1f502.png', [u'\U0001f502']),
        ('u25b6.png', [u'\u25b6']),
        ('u23e9.png', [u'\u23e9']),
        ('u23ed.png', [u'\u23ed']),
        ('u23ef.png', [u'\u23ef']),
        ('u25c0.png', [u'\u25c0']),
        ('u23ea.png', [u'\u23ea']),
        ('u23ee.png', [u'\u23ee']),
        ('u1f53c.png', [u'\U0001f53c']),
        ('u23eb.png', [u'\u23eb']),
        ('u1f53d.png', [u'\U0001f53d']),
        ('u23ec.png', [u'\u23ec']),
        ('u23f8.png', [u'\u23f8']),
        ('u23f9.png', [u'\u23f9']),
        ('u23fa.png', [u'\u23fa']),
        ('u23cf.png', [u'\u23cf']),
        ('u1f3a6.png', [u'\U0001f3a6']),
        ('u1f505.png', [u'\U0001f505']),
        ('u1f506.png', [u'\U0001f506']),
        ('u1f4f6.png', [u'\U0001f4f6']),
        ('u1f4f3.png', [u'\U0001f4f3']),
        ('u1f4f4.png', [u'\U0001f4f4']),

        # subgroup: other-symbol
        ('u2640.png', [u'\u2640']),
        ('u2642.png', [u'\u2642']),
        ('u2695.png', [u'\u2695']),
        ('u267b.png', [u'\u267b']),
        ('u269c.png', [u'\u269c']),
        ('u1f531.png', [u'\U0001f531']),
        ('u1f4db.png', [u'\U0001f4db']),
        ('u1f530.png', [u'\U0001f530']),
        ('u2b55.png', [u'\u2b55']),
        ('u2705.png', [u'\u2705']),
        ('u2611.png', [u'\u2611']),
        ('u2714.png', [u'\u2714']),
        ('u2716.png', [u'\u2716']),
        ('u274c.png', [u'\u274c']),
        ('u274e.png', [u'\u274e']),
        ('u2795.png', [u'\u2795']),
        ('u2796.png', [u'\u2796']),
        ('u2797.png', [u'\u2797']),
        ('u27b0.png', [u'\u27b0']),
        ('u27bf.png', [u'\u27bf']),
        ('u303d.png', [u'\u303d']),
        ('u2733.png', [u'\u2733']),
        ('u2734.png', [u'\u2734']),
        ('u2747.png', [u'\u2747']),
        ('u203c.png', [u'\u203c']),
        ('u2049.png', [u'\u2049']),
        ('u2753.png', [u'\u2753']),
        ('u2754.png', [u'\u2754']),
        ('u2755.png', [u'\u2755']),
        ('u2757.png', [u'\u2757']),
        ('u3030.png', [u'\u3030']),
        ('u00a9.png', [u'\xa9']),
        ('u00ae.png', [u'\xae']),
        ('u2122.png', [u'\u2122']),

        # subgroup: keycap
        (None, [
            ('u0023_20e3.png', [u'\x23\u20e3']),
            ('u002a_20e3.png', [u'\x2a\u20e3']),
            ('u0030_20e3.png', [u'\x30\u20e3']),
            ('u0031_20e3.png', [u'\x31\u20e3']),
            ('u0032_20e3.png', [u'\x32\u20e3']),
            ('u0033_20e3.png', [u'\x33\u20e3']),
            ('u0034_20e3.png', [u'\x34\u20e3']),
            ('u0035_20e3.png', [u'\x35\u20e3']),
            ('u0036_20e3.png', [u'\x36\u20e3']),
            ('u0037_20e3.png', [u'\x37\u20e3']),
            ('u0038_20e3.png', [u'\x38\u20e3']),
            ('u0039_20e3.png', [u'\x39\u20e3']),
            ('u1f51f.png', [u'\U0001f51f']),
            ]),

        # subgroup: alphanum
        ('u1f4af.png', [u'\U0001f4af']),
        ('u1f520.png', [u'\U0001f520']),
        ('u1f521.png', [u'\U0001f521']),
        ('u1f522.png', [u'\U0001f522']),
        ('u1f523.png', [u'\U0001f523']),
        ('u1f524.png', [u'\U0001f524']),
        ('u1f170.png', [u'\U0001f170']),
        ('u1f18e.png', [u'\U0001f18e']),
        ('u1f171.png', [u'\U0001f171']),
        ('u1f191.png', [u'\U0001f191']),
        ('u1f192.png', [u'\U0001f192']),
        ('u1f193.png', [u'\U0001f193']),
        ('u2139.png', [u'\u2139']),
        ('u1f194.png', [u'\U0001f194']),
        ('u24c2.png', [u'\u24c2']),
        ('u1f195.png', [u'\U0001f195']),
        ('u1f196.png', [u'\U0001f196']),
        ('u1f17e.png', [u'\U0001f17e']),
        ('u1f197.png', [u'\U0001f197']),
        ('u1f17f.png', [u'\U0001f17f']),
        ('u1f198.png', [u'\U0001f198']),
        ('u1f199.png', [u'\U0001f199']),
        ('u1f19a.png', [u'\U0001f19a']),
        ('u1f201.png', [u'\U0001f201']),
        ('u1f202.png', [u'\U0001f202']),
        ('u1f237.png', [u'\U0001f237']),
        ('u1f236.png', [u'\U0001f236']),
        ('u1f22f.png', [u'\U0001f22f']),
        ('u1f250.png', [u'\U0001f250']),
        ('u1f239.png', [u'\U0001f239']),
        ('u1f21a.png', [u'\U0001f21a']),
        ('u1f232.png', [u'\U0001f232']),
        ('u1f251.png', [u'\U0001f251']),
        ('u1f238.png', [u'\U0001f238']),
        ('u1f234.png', [u'\U0001f234']),
        ('u1f233.png', [u'\U0001f233']),
        ('u3297.png', [u'\u3297']),
        ('u3299.png', [u'\u3299']),
        ('u1f23a.png', [u'\U0001f23a']),
        ('u1f235.png', [u'\U0001f235']),


        # subgroup: geometric
        ('u25aa.png', [u'\u25aa']),
        ('u25ab.png', [u'\u25ab']),
        ('u25fb.png', [u'\u25fb']),
        ('u25fc.png', [u'\u25fc']),
        ('u25fd.png', [u'\u25fd']),
        ('u25fe.png', [u'\u25fe']),
        ('u2b1b.png', [u'\u2b1b']),
        ('u2b1c.png', [u'\u2b1c']),
        ('u1f536.png', [u'\U0001f536']),
        ('u1f537.png', [u'\U0001f537']),
        ('u1f538.png', [u'\U0001f538']),
        ('u1f539.png', [u'\U0001f539']),
        ('u1f53a.png', [u'\U0001f53a']),
        ('u1f53b.png', [u'\U0001f53b']),
        ('u1f4a0.png', [u'\U0001f4a0']),
        ('u1f518.png', [u'\U0001f518']),
        ('u1f532.png', [u'\U0001f532']),
        ('u1f533.png', [u'\U0001f533']),
        ('u26aa.png', [u'\u26aa']),
        ('u26ab.png', [u'\u26ab']),
        ('u1f534.png', [u'\U0001f534']),
        ('u1f535.png', [u'\U0001f535']),

        ]),

    ('Flags', [
        # group: Flags
        ('u1f3f4.png', None), # Category image

        # subgroup: country-flag
        ('u1f3c1.png', [u'\U0001f3c1']),
        ('u1f6a9.png', [u'\U0001f6a9']),
        ('u1f38c.png', [u'\U0001f38c']),
        ('u1f3f4.png', [u'\U0001f3f4']),
        ('u1f3f3.png', [u'\U0001f3f3']),

        # subgroup: country-flag
        ('u1f1e8_1f1f3.png', [u'\U0001f1e8\U0001f1f3']),
        ('u1f1e9_1f1ea.png', [u'\U0001f1e9\U0001f1ea']),
        ('u1f1ea_1f1f8.png', [u'\U0001f1ea\U0001f1f8']),
        ('u1f1eb_1f1f7.png', [u'\U0001f1eb\U0001f1f7']),
        ('u1f1ec_1f1e7.png', [u'\U0001f1ec\U0001f1e7']),
        ('u1f1ee_1f1f9.png', [u'\U0001f1ee\U0001f1f9']),
        ('u1f1ef_1f1f5.png', [u'\U0001f1ef\U0001f1f5']),
        ('u1f1f0_1f1f7.png', [u'\U0001f1f0\U0001f1f7']),
        ('u1f1f7_1f1fa.png', [u'\U0001f1f7\U0001f1fa']),
        ('u1f1fa_1f1f8.png', [u'\U0001f1fa\U0001f1f8']),

    ]),])


if __name__ == '__main__':

    from PIL import Image
    import sys
    import os

    width = 24
    height = 24
    count = 2200
    columns = 20

    atlas_width = columns * width
    atlas_height = (count / columns) * height

    emoticon_atlas = Image.new("RGBA", (atlas_width, int(atlas_height)))

    column_position = 0
    height_position = 0

    for category in emoticons:

        if not emoticons[category]:
            continue

        for filename, codepoint in emoticons[category]:
            if not filename:
                # We have an emoticon with a modifier
                for mod_filename, mod_codepoint in codepoint:
                    path = os.path.join('png', mod_filename)
                    image = Image.open(path)
                    emoticon_atlas.paste(
                        image, (column_position, height_position))
                    if column_position == (atlas_width - width):
                        height_position += height
                        column_position = 0
                    else:
                        column_position += width
            else:
                path = os.path.join('png', filename)
                image = Image.open(path)
                emoticon_atlas.paste(
                    image, (column_position, height_position))
                if column_position == (atlas_width - width):
                    height_position += height
                    column_position = 0
                else:
                    column_position += width

    emoticon_atlas.save('emoticons.png')

    print('Finished Successful!')
