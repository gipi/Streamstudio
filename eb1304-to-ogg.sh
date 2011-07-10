#!/bin/sh
#
# eb1304-to-ogg.sh - Take 4 input AVFs from a
#                    AVerDiGi EB1304NET and composes them together
#                    into a quad view ogg theora/vorbis video.
#
# Copyright (C) 2009 Ray Strode
#
# Based on guessing and example pipelines found around the internets.

# This file is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; either version 2 of the License,
# or (at your option) any later version.
#
# This file is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this; see the file COPYING.  If not, write to the Free
# Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.

AUDIO_BOOST_FACTOR=200

function usage ()
{
    echo "$0: { -h | [-v] [-a BOOST] [file1.avi file2.avi file3.avi file4.avi] [output.ogg] }" 2>&1
    echo "Each file will be scaled to and positioned in a 720x480 quadrant" 2>&1
    echo 2>&1
    echo "-v	verbose" 2>&1
    echo "-a	Audio boost factor (Default: $AUDIO_BOOST_FACTOR)" 2>&1
}

NUMBER_OF_FILES=0
LAUNCH_ARGS=""
while [ $# -gt 0 ]; do
    case "$1" in
        -v)
            LAUNCH_ARGS="$LAUNCH_ARGS -v"
        ;;

        -a)
            shift
            AUDIO_BOOST_FACTOR="$1"
        ;;

        --help|-h)
            usage
            exit 0
        ;;

        *)
            if [ ! -f "$1" ]; then
                if [ "${1:0:1}" = "-" ]; then
                    usage
                    exit 1
                fi
            fi

            FILES[$NUMBER_OF_FILES]="$1"
            NUMBER_OF_FILES=$[NUMBER_OF_FILES + 1]
        ;;
    esac
    shift
done

if [ $NUMBER_OF_FILES -eq 0 ]; then
    INPUT_VIDEO_1_AND_AUDIO="ch1.avf"
    INPUT_VIDEO_2="ch2.avf"
    INPUT_VIDEO_3="ch3.avf"
    INPUT_VIDEO_4="ch4.avf"
    OUTPUT_FILE="video-`date +%Y.%m.%d-%H.%M.%S`.ogg"
elif [ $NUMBER_OF_FILES -eq 1 ]; then
    INPUT_VIDEO_1_AND_AUDIO="ch1.avf"
    INPUT_VIDEO_2="ch2.avf"
    INPUT_VIDEO_3="ch3.avf"
    INPUT_VIDEO_4="ch4.avf"
    OUTPUT_FILE="${FILES[0]}"
elif [ $NUMBER_OF_FILES -eq 5 ]; then
    INPUT_VIDEO_1_AND_AUDIO="${FILES[0]}"
    INPUT_VIDEO_2="${FILES[1]}"
    INPUT_VIDEO_3="${FILES[2]}"
    INPUT_VIDEO_4="${FILES[3]}"
    OUTPUT_FILE="${FILES[4]}"
else
    usage
    exit 1
fi

gst-launch $LAUNCH_ARGS                                                        \
             filesrc name=upper_left_video_and_audio                           \
                     location=$INPUT_VIDEO_1_AND_AUDIO                         \
                   ! avidemux name=avi_extractor                               \
                   ! multiqueue name=streams                                   \
                                                                               \
             avi_extractor.video_00 ! streams.sink0                            \
             avi_extractor.audio_00 ! streams.sink1                            \
                                                                               \
             oggmux name=ogg_packer                                            \
                    ! filesink location="$OUTPUT_FILE"                         \
                                                                               \
             streams.src1                                                      \
                        ! decodebin                                            \
                        ! audioconvert                                         \
                        ! audioamplify amplification=$AUDIO_BOOST_FACTOR       \
                        ! audioresample                                        \
                        ! audiorate                                            \
                        ! vorbisenc                                            \
                        ! ogg_packer.                                          \
                                                                               \
             streams.src0                                                      \
                        ! decodebin                                            \
                        ! videoscale                                           \
                        ! 'video/x-raw-yuv,width=720,height=480'               \
                        ! videobox right=-720 bottom=-480                      \
                        ! ffmpegcolorspace                                     \
                        ! queue                                                \
                        ! quad_screen.sink_0                                   \
                                                                               \
                                                                               \
             filesrc name=upper_right_video                                    \
                     location=$INPUT_VIDEO_2                                   \
                   ! queue                                                     \
                   ! decodebin                                                 \
                   ! videoscale                                                \
                   ! 'video/x-raw-yuv,width=720,height=480'                    \
                   ! ffmpegcolorspace                                          \
                   ! quad_screen.sink_1                                        \
                                                                               \
                                                                               \
             filesrc name=lower_left_video                                     \
                     location=$INPUT_VIDEO_3                                   \
                   ! queue                                                     \
                   ! decodebin                                                 \
                   ! videoscale                                                \
                   ! 'video/x-raw-yuv,width=720,height=480'                    \
                   ! ffmpegcolorspace                                          \
                   ! quad_screen.sink_2                                        \
                                                                               \
                                                                               \
             filesrc name=lower_right_video                                    \
                     location=$INPUT_VIDEO_4                                   \
                   ! queue                                                     \
                   ! decodebin                                                 \
                   ! videoscale                                                \
                   ! 'video/x-raw-yuv,width=720,height=480'                    \
                   ! ffmpegcolorspace                                          \
                   ! quad_screen.sink_3                                        \
                                                                               \
                                                                               \
             videomixer name=quad_screen                                       \
                        sink_0::xpos=0   sink_0::ypos=0   sink_0::zorder=0     \
                        sink_1::xpos=720 sink_1::ypos=0   sink_1::zorder=1     \
                        sink_2::xpos=0   sink_2::ypos=480 sink_2::zorder=1     \
                        sink_3::xpos=720 sink_3::ypos=480 sink_3::zorder=1     \
                      ! ffmpegcolorspace                                       \
                      ! videorate                                              \
                      ! theoraenc                                              \
                      ! progressreport name="Encoding Progress"                \
                      ! ogg_packer.                                            \
                                                                               \
                                                                               \
                                                                               \

