from lofi_batch.gpu_free import is_gpu_free, parse_nvidia_smi_csv


def test_parse_and_free():
    sample = "0, 2, 50000\n1, 80, 1000\n"
    rows = parse_nvidia_smi_csv(sample)
    assert len(rows) == 2
    assert is_gpu_free(0, util_max=5, mem_free_min_mib=20000, smi_output=sample) is True
    assert is_gpu_free(1, util_max=5, mem_free_min_mib=20000, smi_output=sample) is False
