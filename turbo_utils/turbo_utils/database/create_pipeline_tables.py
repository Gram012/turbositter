'''
Provides postgresql commands to set up the Pipeline database from scratch.

- pipeline.images           - the basic science data for the images
- pipeline.image_status     - the pipeline stats for individual images
- pipeline.processing_time  - the runtime taken by an image at each stage in the pipeline
- pipeline.status           - the total runtime and number of images at each stage in the pipeline
'''

def create_pipeline_tables(database_connection, schema='pipeline'):
    """
    Creates all of the tables for the Pipeline and propagates basic data
    """

    create_pipeline_schema = f"""
    CREATE SCHEMA IF NOT EXISTS {schema} AUTHORIZATION turbogroup;
    """

    create_image_table = f"""
    CREATE TABLE IF NOT EXISTS {schema}.images (
    image_id SERIAL PRIMARY KEY,
    file_path VARCHAR(255) NOT NULL,
    object_id VARCHAR(64) NOT NULL,
    filter VARCHAR(64) NOT NULL,
    ra REAL,
    dec REAL,
    quality VARCHAR(64),
    ncoadds INT,
    nsources INT,
    reference_path VARCHAR(255),
    reference_distance REAL
    );
    """

    set_image_table_owner = f"""
    ALTER TABLE {schema}.images OWNER TO turbogroup;
    """

    create_status_table = f"""
    CREATE TABLE IF NOT EXISTS {schema}.image_status (
    image_id int PRIMARY KEY NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    status VARCHAR (128) NOT NULL,
    processing_time REAL NOT NULL,
    pipeline_step VARCHAR(255) NOT NULL,
    step_message VARCHAR(128),

    FOREIGN KEY (image_id)
        REFERENCES {schema}.images (image_id) ON DELETE CASCADE,
    FOREIGN KEY (pipeline_step)
        REFERENCES {schema}.status (pipeline_step) ON DELETE CASCADE
    );
    """


    add_pipeline_categories = f"""
    INSERT INTO {schema}.status(pipeline_step, shortname, total_runtime, n_processed, n_current)
    VALUES
    ('received', 'receiv', 0, 0, 0),
    ('captured', 'captur', 0, 0, 0)
    ON CONFLICT DO NOTHING;
    """

    set_image_status_owner = f"""
    ALTER TABLE {schema}.image_status OWNER TO turbogroup;
    """

    create_time_table = f"""
    CREATE TABLE IF NOT EXISTS {schema}.processing_time (
    image_id int,
    pipeline_step VARCHAR(255),
    runtime REAL NOT NULL,

    PRIMARY KEY(image_id, pipeline_step),
    FOREIGN KEY (image_id)
        REFERENCES {schema}.images (image_id) ON DELETE CASCADE
    );
    """

    set_time_table_owner = f"""
    ALTER TABLE {schema}.processing_time OWNER TO turbogroup;
    """

    create_pipeline_statistics = f"""
    CREATE TABLE IF NOT EXISTS {schema}.status (
    pipeline_step VARCHAR(255) PRIMARY KEY,
    shortname VARCHAR(25) NOT NULL,
    total_runtime REAL NOT NULL,
    n_processed INT NOT NULL,
    n_current INT NOT NULL
    );
    """

    set_status_table_owner = f"""
    ALTER TABLE {schema}.status OWNER TO turbogroup;
    """

    create_flats_table = f"""
    CREATE TABLE IF NOT EXISTS {schema}.flats (
    image_id SERIAL PRIMARY KEY,
    file_path VARCHAR(255) NOT NULL,
    object_id VARCHAR(64) NOT NULL,
    telescope VARCHAR(16) NOT NULL,
    filter CHAR(1) NOT NULL,
    type CHAR(4) NOT NULL,
    date_obs TIMESTAMPTZ NOT NULL,
    downloaded BOOLEAN NOT NULL
    );
    """

    set_flats_table_owner = f"""
    ALTER TABLE {schema}.flats OWNER TO turbogroup;
    """

    create_darks_table = f"""
    CREATE TABLE IF NOT EXISTS {schema}.darks (
    image_id SERIAL PRIMARY KEY,
    file_path VARCHAR(255) NOT NULL,
    object_id VARCHAR(64) NOT NULL,
    camera VARCHAR(255) NOT NULL,
    date_obs TIMESTAMP
    );
    """

    set_darks_table_owner = f"""
    ALTER TABLE {schema}.darks OWNER TO turbogroup;
    """

    create_biases_table = f"""
    CREATE TABLE IF NOT EXISTS {schema}.biases (
    image_id SERIAL PRIMARY KEY,
    file_path VARCHAR(255) NOT NULL,
    object_id VARCHAR(64) NOT NULL,
    camera VARCHAR(255) NOT NULL,
    date_obs TIMESTAMP
    );
    """

    set_biases_table_owner = f"""
    ALTER TABLE {schema}.biases OWNER TO turbogroup;
    """

    create_candidates_table = f"""
    CREATE TABLE IF NOT EXISTS {schema}.candidates (
    image_id INT NOT NULL,
    ra REAL,
    dec REAL,
    ra_cand REAL,
    dec_cand REAL,
    mag_cand REAL,
    dmag_cand REAL,
    real_bogus REAL,
    sci_cutout_path VARCHAR NOT NULL,
    ref_cutout_path VARCHAR NOT NULL,
    sub_cutout_path VARCHAR NOT NULL,
    date_obs TIMESTAMP,
    object_id VARCHAR(64) NOT NULL,
    PRIMARY KEY(image_id, object_id)
    );
    """

    create_scamp_table = f"""
    CREATE TABLE IF NOT EXISTS {schema}.scamp_results (
    image_id INT NOT NULL,
    object_id VARCHAR(64),
    ra REAL,
    dec REAL,
    date_proc TIMESTAMP NOT NULL,
    astrom_offset_ref REAL[],
    astrom_sigma_ref REAL[],
    astrom_corr_ref REAL,
    astrom_chi_ref REAL,
    dist_map_path VARCHAR,
    fgroup_map_path VARCHAR,
    referr_1d_path VARCHAR,
    referr_2d_path VARCHAR,
    PRIMARY KEY(image_id, date_proc)
    );
    """


    table_commands = [create_pipeline_schema,
                      create_image_table, set_image_table_owner,
                      create_pipeline_statistics, set_status_table_owner,
                      create_status_table, set_image_status_owner,
                      create_time_table, set_time_table_owner,
                      create_flats_table, set_flats_table_owner,
                      create_darks_table, set_darks_table_owner,
                      create_biases_table, set_biases_table_owner,
                      create_candidates_table, create_scamp_table, add_pipeline_categories]

    cursor = database_connection.cursor()
    commands = table_commands
    # run the table creation commands
    for command in commands:
        try:
            cursor.execute(command)
        except Exception as e:
            print(e)
            print(command)


    # close the cursor and commit
    cursor.close()
    database_connection.commit()
