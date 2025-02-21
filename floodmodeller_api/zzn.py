"""
Flood Modeller Python API
Copyright (C) 2023 Jacobs U.K. Limited

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License 
as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty 
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. 

You should have received a copy of the GNU General Public License along with this program.  If not, see https://www.gnu.org/licenses/.

If you have any query about this program or this License, please contact us at support@floodmodeller.com or write to the following 
address: Jacobs UK Limited, Flood Modeller, Cottons Centre, Cottons Lane, London, SE1 2QG, United Kingdom.
"""

import ctypes as ct
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import numpy as np

from ._base import FMFile


class ZZN(FMFile):
    """Reads and processes Flood Modeller 1D binary results format '.zzn'

    Args:
        zzn_filepath (str): Full filepath to model zzn file

    Output:
        Initiates 'ZZN' class object
    """

    _filetype: str = "ZZN"
    _suffix: str = ".zzn"

    def __init__(self, zzn_filepath: Optional[Union[str, Path]]):
        try:
            self._filepath = zzn_filepath
            FMFile.__init__(self)

            # Get zzn_dll path
            zzn_dll = Path(Path(__file__).resolve().parent, "zzn_read.dll")
            # Using str() method as CDLL doesn't seem to like accepting Path object
            zzn_read = ct.CDLL(str(zzn_dll))

            # Get zzl path
            zzn = self._filepath
            zzl = zzn.with_suffix(".zzl")
            if not zzl.exists():
                raise FileNotFoundError(
                    "Error: Could not find associated .ZZL file. Ensure that the zzn results have an associated zzl file with matching name."
                )

            self.meta = {}  # Dict object to hold all metadata
            self.data = {}  # Dict object to hold all data

            # PROCESS_ZZL
            self.meta["zzl_name"] = ct.create_string_buffer(
                bytes(str(zzl), "utf-8"), 255
            )
            self.meta["zzn_name"] = ct.create_string_buffer(
                bytes(str(zzn), "utf-8"), 255
            )
            self.meta["model_title"] = ct.create_string_buffer(b"", 128)
            self.meta["nnodes"] = ct.c_int(0)
            self.meta["label_length"] = ct.c_int(0)
            self.meta["dt"] = ct.c_float(0.0)
            self.meta["timestep0"] = ct.c_int(0)
            self.meta["ltimestep"] = ct.c_int(0)
            self.meta["save_int"] = ct.c_float(0.0)
            self.meta["is_quality"] = ct.c_bool(False)
            self.meta["nvars"] = ct.c_int(0)
            self.meta["tzero"] = (ct.c_int * 5)()
            self.meta["errstat"] = ct.c_int(0)
            zzn_read.PROCESS_ZZL(
                ct.byref(self.meta["zzl_name"]),
                ct.byref(self.meta["model_title"]),
                ct.byref(self.meta["nnodes"]),
                ct.byref(self.meta["label_length"]),
                ct.byref(self.meta["dt"]),
                ct.byref(self.meta["timestep0"]),
                ct.byref(self.meta["ltimestep"]),
                ct.byref(self.meta["save_int"]),
                ct.byref(self.meta["is_quality"]),
                ct.byref(self.meta["nvars"]),
                ct.byref(self.meta["tzero"]),
                ct.byref(self.meta["errstat"]),
            )
            # PROCESS_LABELS
            self.meta["labels"] = (
                ct.c_char * self.meta["label_length"].value * self.meta["nnodes"].value
            )()
            zzn_read.PROCESS_LABELS(
                ct.byref(self.meta["zzl_name"]),
                ct.byref(self.meta["nnodes"]),
                ct.byref(self.meta["labels"]),
                ct.byref(self.meta["label_length"]),
                ct.byref(self.meta["errstat"]),
            )
            # PREPROCESS_ZZN
            last_hr = (
                (self.meta["ltimestep"].value - self.meta["timestep0"].value)
                * self.meta["dt"].value
                / 3600
            )
            self.meta["output_hrs"] = (ct.c_float * 2)(0.0, last_hr)
            self.meta["aitimestep"] = (ct.c_int * 2)(
                self.meta["timestep0"].value, self.meta["ltimestep"].value
            )
            self.meta["isavint"] = (ct.c_int * 2)()
            zzn_read.PREPROCESS_ZZN(
                ct.byref(self.meta["output_hrs"]),
                ct.byref(self.meta["aitimestep"]),
                ct.byref(self.meta["dt"]),
                ct.byref(self.meta["timestep0"]),
                ct.byref(self.meta["ltimestep"]),
                ct.byref(self.meta["save_int"]),
                ct.byref(self.meta["isavint"]),
            )
            # PROCESS_ZZN
            self.meta["node_ID"] = ct.c_int(-1)
            self.meta["savint_skip"] = ct.c_int(1)
            self.meta["savint_range"] = ct.c_int(
                int(
                    (
                        (self.meta["isavint"][1] - self.meta["isavint"][0])
                        / self.meta["savint_skip"].value
                    )
                )
            )
            nx = self.meta["nnodes"].value
            ny = self.meta["nvars"].value
            nz = self.meta["savint_range"].value + 1
            self.data["all_results"] = (ct.c_float * nx * ny * nz)()
            self.data["max_results"] = (ct.c_float * nx * ny)()
            self.data["min_results"] = (ct.c_float * nx * ny)()
            self.data["max_times"] = (ct.c_int * nx * ny)()
            self.data["min_times"] = (ct.c_int * nx * ny)()
            zzn_read.PROCESS_ZZN(
                ct.byref(self.meta["zzn_name"]),
                ct.byref(self.meta["node_ID"]),
                ct.byref(self.meta["nnodes"]),
                ct.byref(self.meta["is_quality"]),
                ct.byref(self.meta["nvars"]),
                ct.byref(self.meta["savint_range"]),
                ct.byref(self.meta["savint_skip"]),
                ct.byref(self.data["all_results"]),
                ct.byref(self.data["max_results"]),
                ct.byref(self.data["min_results"]),
                ct.byref(self.data["max_times"]),
                ct.byref(self.data["min_times"]),
                ct.byref(self.meta["errstat"]),
                ct.byref(self.meta["isavint"]),
            )

            # Convert useful metadata from C types into python types

            self.meta["dt"] = self.meta["dt"].value
            self.meta["nnodes"] = self.meta["nnodes"].value
            self.meta["save_int"] = self.meta["save_int"].value
            self.meta["nvars"] = self.meta["nvars"].value
            self.meta["savint_range"] = self.meta["savint_range"].value

            self.meta["zzn_name"] = self.meta["zzn_name"].value.decode()
            self.meta["labels"] = [
                label.value.decode().strip() for label in list(self.meta["labels"])
            ]
            self.meta["model_title"] = self.meta["model_title"].value.decode()

        except Exception as e:
            self._handle_exception(e, when="read")

    def to_dataframe(
        self,
        result_type: Optional[str] = "all",
        variable: Optional[str] = "all",
        include_time: Optional[bool] = False,
        multilevel_header: Optional[bool] = True,
    ) -> pd.DataFrame:
        """Loads zzn results to pandas dataframe object.

        Args:
            result_type (str, optional): {'all'} | 'max' | 'min'
                Define whether to return all timesteps or just max/min results. Defaults to 'all'.
            variable (str, optional): {'all'} | 'Flow' | 'Stage' | 'Froude' | 'Velocity' | 'Mode' | 'State'
                Specify a single output variable (e.g 'flow' or 'stage'). Defaults to 'all'.
            include_time (bool, optional):
                Whether to include the time of max or min results. Defaults to False.
            multilevel_header (bool, optional): If True, the returned dataframe will have multi-level column
                headers with the variable as first level and node label as second header. If False, the column
                names will be formatted "{node label}_{variable}". Defaults to True.

        Returns:
            pandas.DataFrame(): dataframe object of simulation results
        """
        nx = self.meta["nnodes"]
        ny = self.meta["nvars"]
        nz = self.meta["savint_range"] + 1
        result_type = result_type.lower()

        if result_type == "all":

            arr = np.array(self.data["all_results"])
            time_index = np.linspace(
                self.meta["output_hrs"][0], self.meta["output_hrs"][1], nz
            )
            vars = ["Flow", "Stage", "Froude", "Velocity", "Mode", "State"]
            if multilevel_header:
                col_names = [vars, self.meta["labels"]]
                df = pd.DataFrame(
                    arr.reshape(nz, nx * ny),
                    index=time_index,
                    columns=pd.MultiIndex.from_product(col_names),
                )
                df.index.name = "Time (hr)"
                if not variable == "all":
                    return df[variable.capitalize()]

            else:
                col_names = [
                    f"{node}_{var}" for var in vars for node in self.meta["labels"]
                ]
                df = pd.DataFrame(
                    arr.reshape(nz, nx * ny), index=time_index, columns=col_names
                )
                df.index.name = "Time (hr)"
                if not variable == "all":
                    use_cols = [
                        col for col in df.columns if col.endswith(variable.capitalize())
                    ]
                    return df[use_cols]
            return df

        elif (result_type == "max") or (result_type == "min"):
            arr = np.array(self.data[f"{result_type}_results"]).transpose()
            node_index = self.meta["labels"]
            col_names = [
                result_type.capitalize() + lbl
                for lbl in [
                    " Flow",
                    " Stage",
                    " Froude",
                    " Velocity",
                    " Mode",
                    " State",
                ]
            ]
            df = pd.DataFrame(arr, index=node_index, columns=col_names)
            df.index.name = "Node Label"

            if include_time:
                times = np.array(self.data[f"{result_type}_times"]).transpose()
                # transform timestep into hrs
                times = ((times - self.meta["timestep0"]) * self.meta["dt"]) / 3600
                time_col_names = [name + " Time(hrs)" for name in col_names]
                time_df = pd.DataFrame(times, index=node_index, columns=time_col_names)
                time_df.index.name = "Node Label"
                df = pd.concat([df, time_df], axis=1)
                new_col_order = [
                    x for y in list(zip(col_names, time_col_names)) for x in y
                ]
                df = df[new_col_order]
                if not variable == "all":
                    return df[
                        [
                            f"{result_type.capitalize()} {variable.capitalize()}",
                            f"{result_type.capitalize()} {variable.capitalize()} Time(hrs)",
                        ]
                    ]
                return df

            if not variable == "all":
                return df[f"{result_type.capitalize()} {variable.capitalize()}"]
            return df

        else:
            raise ValueError(f'Result type: "{result_type}" not recognised')

    def export_to_csv(
        self,
        save_location: Optional[Union[str, Path]] = "default",
        result_type: Optional[str] = "all",
        variable: Optional[str] = "all",
        include_time: Optional[bool] = False,
    ) -> None:
        """Exports zzn results to CSV file.

        Args:
            save_location (str, optional): {default} | folder or file path
                Full or relative path to folder or csv file to save output csv, if no argument given or if set to 'default' then CSV will be saved in same location as ZZN file. Defaults to 'default'.
            result_type (str, optional): {all} | max | min
                Define whether to output all timesteps or just max/min results. Defaults to 'all'.
            variable (str, optional): {'all'} | 'Flow' | 'Stage' | 'Froude' | 'Velocity' | 'Mode' | 'State'
                Specify a single output variable (e.g 'flow' or 'stage'). Defaults to 'all'.
            include_time (bool, optional):
                Whether to include the time of max or min results. Defaults to False.

        Raises:
            Exception: Raised if result_type set to invalid option
        """
        if save_location == "default":
            save_location = Path(self.meta["zzn_name"]).with_suffix(".csv")
        else:
            save_location = Path(save_location)
            if not save_location.is_absolute():
                # for if relative folder path given
                save_location = Path(Path(self.meta["zzn_name"]).parent, save_location)

        if not save_location.suffix == ".csv":  # Assumed to be pointing to a folder
            # Check if the folder exists, if not create it
            if not save_location.exists():
                Path.mkdir(save_location)
            save_location = Path(
                save_location, Path(self.meta["zzn_name"]).with_suffix(".csv").name
            )

        else:
            if not save_location.parent.exists():
                Path.mkdir(save_location.parent)

        result_type = result_type.lower()

        if not result_type.lower() in ["all", "max", "min"]:
            raise Exception(
                f" '{result_type}' is not a valid result type. Valid arguments are: 'all', 'max' or 'min' "
            )

        df = self.to_dataframe(
            result_type=result_type, variable=variable, include_time=include_time
        )
        df.to_csv(save_location)
        print(f"CSV saved to {save_location}")

    def to_dict_of_dataframes(self, variable: Optional[str] = "all") -> dict:
        """Loads zzn results to a dictionary of pandas dataframe objects.

        Args:
            variable (str, optional): {'all'} | 'Flow' | 'Stage' | 'Froude' | 'Velocity' | 'Mode' | 'State'
                Specify a single output variable (e.g 'flow' or 'stage') or any combination passed as comma separated
                variable names. Defaults to 'all'.

        Returns:
            dict: dictionary of dataframe object of simulation results, keys corresponding to variables.
        """
        nx = self.meta["nnodes"]
        ny = self.meta["nvars"]
        nz = self.meta["savint_range"] + 1
        output = {}

        arr = np.array(self.data["all_results"])
        time_index = np.linspace(
            self.meta["output_hrs"][0], self.meta["output_hrs"][1], nz
        )

        vars = ["Flow", "Stage", "Froude", "Velocity", "Mode", "State"]

        col_names = self.meta["labels"]
        temp_arr = np.reshape(arr, (nz, ny, nx))

        for i, var in enumerate(vars):
            output[var] = pd.DataFrame(
                temp_arr[:, i, :], index=time_index, columns=col_names
            )
            output[var].index.name = "Time (hr)"

        output["Time (hr)"] = time_index

        if variable != "all":
            input_vars = variable.split(",")
            for i, var in enumerate(input_vars):
                input_vars[i] = var.strip().capitalize()
                if not input_vars[i] in vars:
                    raise Exception(
                        f" '{input_vars[i]}' is not a valid variable name. Valid arguments are: {vars} "
                    )

            for var in vars:
                if not var in input_vars:
                    del output[var]
        return output
