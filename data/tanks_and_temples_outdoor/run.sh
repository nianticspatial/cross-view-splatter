declare -a SCENES=("Barn" "Courthouse" "Family" "Francis" "Horse" "Ignatius" "Lighthouse" "Playground" "Temple" "Truck" )


for scene in "${SCENES[@]}"; do
	DATASET_PATH=colmap/$scene
	
	CUDA_VISIBLE_DEVICES=0 colmap feature_extractor \
	       --database_path $DATASET_PATH/database.db \
	        --image_path $DATASET_PATH/images
	
	CUDA_VISIBLE_DEVICES=0 colmap exhaustive_matcher \
	       --database_path $DATASET_PATH/database.db
	
	mkdir -p $DATASET_PATH/sparse/0
	
	CUDA_VISIBLE_DEVICES=0 colmap point_triangulator \
	    --database_path $DATASET_PATH/database.db \
	    --image_path $DATASET_PATH/images \
	    --input_path $DATASET_PATH/input_sparse/0 \
	    --output_path $DATASET_PATH/sparse/0 \
	    --Mapper.tri_ignore_two_view_tracks 0 \
	    --Mapper.init_min_tri_angle 8 \
	
	mv $DATASET_PATH/sparse ~/datasets/tanks_and_temples_outdoor/colmap/$scene/
done
