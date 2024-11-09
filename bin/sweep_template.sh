#!/bin/bash

set -Eeuo pipefail

tmux_session="HighDim"
GPUS=(0 1)

H="4096"
S="2048"
T="2048"
p="0.5"

LR_POLICY="1e-3 1e-4"
WEIGHT_DECAY="true"

group="Optim"

epoch=50000

loss="avargrad"

count=0

for lr_policy in ${LR_POLICY[@]}; do
    for weight_decay in ${WEIGHT_DECAY[@]}; do
        gpu_id=${GPUS[$count]}

        experiment="AnnealedDB/OnPolicy/GFN"
        energy="ManyWell512"

        model_cfg="\
            model.forward_model.hidden_dim=$H \
            model.forward_model.num_layers=4 \
            model.langevin_scaler=null \
            model.state_encoder.s_emb_dim=$S \
            model.time_encoder.t_emb_dim=$T \
            model.prior_energy.std=$p \
            model.annealing_schedule=null \
            "
        model_cfg=$(echo "$model_cfg" | tr -s '[:space:]' ' ' | sed 's/^ *//; s/ *$//')

        optim_cfg="\
            model.optimizer_cfg.lr_policy=$lr_policy\
            model.optimizer_cfg.use_weight_decay=$weight_decay \
            "
        optim_cfg=$(echo "$optim_cfg" | tr -s '[:space:]' ' ' | sed 's/^ *//; s/ *$//')

        ARGS="experiment=$experiment train.fwd_loss=$loss energy=$energy $model_cfg $optim_cfg +group_tag=$group train.epochs=$epoch"

        tmux new-window -t $tmux_session: bash
        tmux send-keys -t $tmux_session: "CUDA_VISIBLE_DEVICES=${gpu_id} python3 sampler/train.py ${ARGS}" C-m

        count=$(( count+1 ))
    done
done