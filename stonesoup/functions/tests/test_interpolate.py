import datetime

import numpy as np
import pytest

from ..interpolate import time_range, interpolate_state_mutable_sequence
from ...types.state import State, StateMutableSequence, GaussianState, StateVector


@pytest.mark.parametrize("input_kwargs, expected",
                         [(dict(start_time=datetime.datetime(2023, 1, 1, 0, 0),
                                end_time=datetime.datetime(2023, 1, 1, 0, 0, 35),
                                timestep=datetime.timedelta(seconds=7)),
                           [datetime.datetime(2023, 1, 1, 0, 0),
                            datetime.datetime(2023, 1, 1, 0, 0, 7),
                            datetime.datetime(2023, 1, 1, 0, 0, 14),
                            datetime.datetime(2023, 1, 1, 0, 0, 21),
                            datetime.datetime(2023, 1, 1, 0, 0, 28),
                            datetime.datetime(2023, 1, 1, 0, 0, 35)
                            ]
                           ),
                          (dict(start_time=datetime.datetime(1970, 1, 1, 0, 0),
                                end_time=datetime.datetime(1970, 1, 1, 0, 0, 6)),
                           [datetime.datetime(1970, 1, 1, 0, 0),
                            datetime.datetime(1970, 1, 1, 0, 0, 1),
                            datetime.datetime(1970, 1, 1, 0, 0, 2),
                            datetime.datetime(1970, 1, 1, 0, 0, 3),
                            datetime.datetime(1970, 1, 1, 0, 0, 4),
                            datetime.datetime(1970, 1, 1, 0, 0, 5),
                            datetime.datetime(1970, 1, 1, 0, 0, 6)
                            ]
                           )
                          ])
def test_time_range(input_kwargs, expected):
    generated_times = list(time_range(**input_kwargs))
    assert generated_times == expected


t0 = datetime.datetime(2023, 9, 1)
t_max = t0 + datetime.timedelta(seconds=10)
out_of_range_time = t_max + datetime.timedelta(seconds=10)


def calculate_state(time: datetime.datetime) -> State:
    """ This function maps a datetime.datetime to a State. This allows interpolated values to be
    checked easily. """
    n_seconds = (time-t0).seconds
    return State(
        timestamp=time,
        state_vector=[
            10 + n_seconds*1.3e-4,
            94 - n_seconds*4.7e-5,
            106 + n_seconds/43,
        ]
    )


@pytest.fixture
def gen_test_data() -> tuple[StateMutableSequence, list[datetime.datetime]]:

    sms = StateMutableSequence([calculate_state(time)
                                for time in time_range(t0, t_max, datetime.timedelta(seconds=0.25))
                                ])

    interp_times = list(time_range(t0, t_max, datetime.timedelta(seconds=0.1)))

    return sms, interp_times


def test_interpolate_state_mutable_sequence(gen_test_data):
    sms, interp_times = gen_test_data
    new_sms = interpolate_state_mutable_sequence(sms, interp_times)

    assert isinstance(new_sms, StateMutableSequence)

    for state in new_sms:
        interp_sv = state.state_vector
        true_sv = calculate_state(state.timestamp).state_vector
        np.testing.assert_allclose(interp_sv, true_sv, rtol=1e-3, atol=1e-7)


def test_interpolate_individual_time(gen_test_data):
    sms, interp_times = gen_test_data

    for time in interp_times[0:50]:
        interp_state = interpolate_state_mutable_sequence(sms, time)

        assert isinstance(interp_state, State)

        interp_sv = interp_state.state_vector
        true_sv = calculate_state(time).state_vector
        np.testing.assert_allclose(interp_sv, true_sv, rtol=1e-3, atol=1e-7)


def test_interpolate_warning(gen_test_data):
    sms, _ = gen_test_data
    times = [t0, t_max, out_of_range_time]

    with pytest.warns(UserWarning):
        _ = interpolate_state_mutable_sequence(sms, times)


def test_interpolate_error(gen_test_data):
    sms, _ = gen_test_data
    time = out_of_range_time

    with pytest.raises(IndexError):
        _ = interpolate_state_mutable_sequence(sms, time)


def test_interpolate_state_other_properties():
    float_times = [0, 0.1, 0.4, 0.9, 1.6, 2.5, 3.6, 4.9, 6.4, 8.1, 10]

    sms = StateMutableSequence([GaussianState(state_vector=[t],
                                              covar=[[t]],
                                              timestamp=t0+datetime.timedelta(seconds=t))
                                for t in float_times
                                ])

    interp_float_times = [0, 2, 4, 6, 8, 10]
    interp_datetime_times = [t0+datetime.timedelta(seconds=t) for t in interp_float_times]

    new_sms = interpolate_state_mutable_sequence(sms, interp_datetime_times)

    # Test state vector and times
    for expected_value, state in zip(interp_float_times, new_sms.states):
        assert state.timestamp == t0 + datetime.timedelta(seconds=expected_value)
        # assert state.state_vector[0] == expected_value
        np.testing.assert_allclose(state.state_vector, StateVector([expected_value]))
        assert isinstance(state, GaussianState)

    # Test Covariances
    # Ideally the covariance should be the same as the state vector. However interpolating the
    # covariance is not implemented and probably shouldn't be. Instead the current method uses the
    # previous state’s covariance. In the future it may be better to use the closest state’s
    # covariance. Therefore these tests are purposely quite lax and only check the covariance
    # value is within a sensible range.

    assert new_sms[0].covar[0][0] == 0  # t=0
    assert 1.6 <= new_sms[1].covar[0][0] <= 2.5  # t=2
    assert 3.6 <= new_sms[2].covar[0][0] <= 4.9  # t=4
    assert 4.9 <= new_sms[3].covar[0][0] <= 6.4  # t=6
    assert 6.4 <= new_sms[4].covar[0][0] <= 8.1  # t=8
    assert new_sms[5].covar[0][0] == 10  # t=10
