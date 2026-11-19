"""Check transfer ASR conditioning and image-paired uncertainty estimates."""

import json
import unittest

import numpy as np

from course_tools.v1_metrics import paired_bootstrap, summarise_predictions


class V1MetricTests(unittest.TestCase):
    def test_asr_excludes_originally_incorrect_images(self):
        result = summarise_predictions([0, 1, 2, 1], [0, 0, 2, 1], [1, 2, 2, 0])
        self.assertEqual(result["clean_accuracy"], 0.75)
        self.assertEqual(result["robust_accuracy"], 0.25)
        self.assertEqual(result["asr_numerator"], 2)
        self.assertEqual(result["asr_denominator"], 3)
        self.assertAlmostEqual(result["asr"], 2 / 3)

    def test_accuracy_uses_all_images_even_when_attack_corrects_a_clean_error(self):
        result = summarise_predictions([0, 1, 2, 1], [0, 0, 2, 1], [1, 1, 2, 1])
        self.assertEqual(result["robust_accuracy"], 0.75)
        self.assertEqual(result["asr_numerator"], 1)
        self.assertAlmostEqual(result["asr"], 1 / 3)

    def test_zero_clean_correct_denominator_is_null(self):
        result = summarise_predictions([0, 1], [1, 0], [1, 0])
        self.assertIsNone(result["asr"])
        self.assertEqual(result["asr_denominator"], 0)
        json.dumps(result, allow_nan=False)

    def test_seed_aggregation_is_mean_not_union_of_successes(self):
        result = summarise_predictions(
            [0, 1, 2, 3], [0, 1, 2, 3], [[1, 1, 2, 3], [0, 0, 2, 3]]
        )
        self.assertEqual(result["attack_seed_count"], 2)
        self.assertEqual(result["asr_numerator"], 1.0)
        self.assertEqual(result["asr"], 0.25)
        self.assertEqual(result["robust_accuracy"], 0.75)
        self.assertEqual([r["asr_numerator"] for r in result["per_seed"]], [1, 1])

    def test_known_paired_difference_has_degenerate_interval(self):
        result = paired_bootstrap([0, 1, 2], [0, 1, 2], [1, 2, 0], [0, 1, 2])
        self.assertEqual(result["asr_a"], 1.0)
        self.assertEqual(result["asr_b"], 0.0)
        self.assertEqual(result["difference_a_minus_b"], 1.0)
        self.assertEqual(result["ci95"], [1.0, 1.0])
        self.assertEqual(result["bootstrap_valid"], 2000)

    def test_identical_methods_remain_paired_in_every_bootstrap(self):
        predictions = [[1, 1, 1, 0], [0, 0, 1, 0]]
        result = paired_bootstrap([0, 1, 0, 1], [0, 1, 0, 0], predictions, predictions)
        self.assertEqual(result["difference_a_minus_b"], 0.0)
        self.assertEqual(result["ci95"], [0.0, 0.0])

    def test_repeating_the_same_attack_seeds_does_not_inflate_evidence(self):
        labels = [0, 1, 0, 1, 0, 1]
        clean = [0, 1, 0, 1, 1, 1]
        adv_a = np.array([[1, 1, 0, 0, 1, 1], [0, 0, 1, 1, 0, 1]])
        adv_b = np.array([[0, 0, 0, 1, 1, 1], [0, 1, 1, 1, 1, 1]])
        once = paired_bootstrap(labels, clean, adv_a, adv_b, seed=7)
        repeated = paired_bootstrap(
            labels, clean, np.tile(adv_a, (4, 1)), np.tile(adv_b, (4, 1)), seed=7
        )
        for key in ("asr_a", "asr_b", "difference_a_minus_b", "ci95", "bootstrap_valid"):
            self.assertEqual(once[key], repeated[key])

    def test_zero_denominator_replicates_are_counted(self):
        result = paired_bootstrap(
            [0, 1], [0, 0], [1, 1], [0, 0], seed=13, n_bootstrap=200
        )
        self.assertGreater(result["bootstrap_valid"], 0)
        self.assertGreater(result["bootstrap_skipped_zero_denominator"], 0)
        self.assertEqual(
            result["bootstrap_valid"] + result["bootstrap_skipped_zero_denominator"], 200
        )
        self.assertEqual(result["ci95"], [1.0, 1.0])

    def test_zero_denominator_pair_returns_json_nulls(self):
        result = paired_bootstrap([0, 1], [1, 0], [1, 0], [0, 1], n_bootstrap=32)
        self.assertIsNone(result["difference_a_minus_b"])
        self.assertIsNone(result["ci95"])
        self.assertEqual(result["bootstrap_valid"], 0)
        self.assertEqual(result["bootstrap_skipped_zero_denominator"], 32)
        json.dumps(result, allow_nan=False)

    def test_different_seed_counts_and_integer_valued_floats_are_supported(self):
        result = paired_bootstrap(
            [0.0, 1.0], [0.0, 1.0], [[1, 1], [0, 0]], [0, 1], n_bootstrap=16
        )
        self.assertEqual(result["asr_a"], 0.5)
        self.assertEqual(result["asr_b"], 0.0)
        self.assertEqual(result["ci95"], [0.5, 0.5])
        json.dumps(result, allow_nan=False)

    def test_bad_labels_and_shapes_are_rejected(self):
        invalid = (
            ([], [], []),
            ([0, 1], [0], [0, 1]),
            ([0, 1], [0, 1], [[0], [1]]),
            ([0, 1], [0, 1], np.empty((0, 2))),
            ([[0, 1]], [0, 1], [0, 1]),
            ([0, 1], [0, 1], [[[0, 1]]]),
            ([0, np.nan], [0, 1], [0, 1]),
            ([0, 1], [0, np.inf], [0, 1]),
            ([0, 1], [0, 1], [0, np.nan]),
            ([-1, 1], [0, 1], [0, 1]),
            ([0.5, 1], [0, 1], [0, 1]),
            ([False, True], [0, 1], [0, 1]),
            (["0", "1"], [0, 1], [0, 1]),
        )
        for arguments in invalid:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    summarise_predictions(*arguments)

    def test_bad_bootstrap_arguments_are_rejected(self):
        for value in (0, -1, 1.2, True):
            with self.subTest(n_bootstrap=value):
                with self.assertRaises(ValueError):
                    paired_bootstrap([0], [0], [1], [0], n_bootstrap=value)
        for value in (-1, 1.2, True):
            with self.subTest(seed=value):
                with self.assertRaises(ValueError):
                    paired_bootstrap([0], [0], [1], [0], seed=value)
        with self.assertRaises(ValueError):
            paired_bootstrap([0], [0], [1], [0, 1])


if __name__ == "__main__":
    unittest.main()
