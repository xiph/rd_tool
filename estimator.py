import json
import os
import threading
import warnings
from numpy.polynomial import polynomial as poly

# A global lock used to preventing estimator data files from being read and written to a the same time.
estimator_file_lock = threading.Lock()

# Classes that extend Estimator assume that work is of a correlated type (i.e. RDEstimator has RDWork)
class Estimator:
    def __init__(self):
        pass
    def update(self, work, time):
        pass
    def get_estimate(self, work):
        return 0
    def finish(self):
        pass

class RDEstimator(Estimator):
    def __init__(self, run):
        super().__init__()
        self.run = run
        self.ref_scale = 0.0
        self.data = None
        input_filename = 'estimate_data/rd/{}/{}.json'.format(run.codec, run.set)
        if os.path.isfile(input_filename):
            with estimator_file_lock:
                input_file = open(input_filename,'r',encoding='utf-8')
                input_json = json.load(input_file)
                input_file.close()
            self.ref_scale = input_json['scale']
            data = {}
            for filename_to_quality in input_json['videos'].items():
                qualities = []
                ratios = []
                for quality_to_ratio in filename_to_quality[1].items():
                    qualities.append(int(quality_to_ratio[0]))
                    ratios.append(quality_to_ratio[1])
                with warnings.catch_warnings():
                    # ignore the RankWarning that polyfit emits
                    warnings.simplefilter('ignore')
                    data[filename_to_quality[0]] = poly.Polynomial(poly.polyfit(qualities, ratios, 5))
            self.data = data
        self.scale = 0.0
        self.sample_sum = 0
        self.sample_counter = 0
    def update(self, work, time):
        ratio = 1.0
        if self.data:
            ratio = self.data[work.filename](work.quality)
        # time/ratio is the scale that would have been correct for the given work
        # the scale is then weighted be the time it took
        self.sample_sum += (time/ratio) * time
        self.sample_counter += time
        self.scale = self.sample_sum/self.sample_counter
    def get_estimate(self, work):
        ratio = 1.0
        if self.data:
            ratio = self.data[work.filename](work.quality)
            if self.sample_counter == 0:
                return ratio * self.ref_scale
        return ratio * self.scale

# Extend RDEstimator since we still want an estimate
class RDDataCollector(RDEstimator):
    def __init__(self, run, video_filenames):
        super().__init__(run)
        collected_data = {}
        for filename in video_filenames:
            #todo: use sorted array on the other side
            collected_data[filename] = {}
        self.collected_data = collected_data
        self.longest_work = 0.0
    def update(self, work, time):
        super().update(work, time)
        self.collected_data[work.filename][work.quality] = time
        self.longest_work = max(self.longest_work, time)
    def finish(self):
        run = self.run
        data_json = {}
        data_json['scale'] = self.longest_work
        videos_json = {}
        for filename_to_quality in self.collected_data.items():
            qualities_json = {}
            for quality_to_time in filename_to_quality[1].items():
                qualities_json[str(quality_to_time[0])] = quality_to_time[1] / self.longest_work
            videos_json[filename_to_quality[0]] = qualities_json
        data_json['videos'] = videos_json
        output_filename = 'estimate_data/rd/{}/{}.json'.format(run.codec, run.set)
        with estimator_file_lock:
            try:
                os.makedirs(os.path.dirname(output_filename), exist_ok=True)
                output_file = open(output_filename,'w',encoding='utf-8')
                json.dump(data_json, output_file)
            except Exception as e:
                pass
        output_file.close()
