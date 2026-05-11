import dataclasses
import datetime
import mysql.connector
import matplotlib.pyplot as plt
from mysqlSecrets import databaseLoginSecrets, MySQLSecrets

PAR_DEFINE_MAX_SAMPLES_PROCESSED_PER_RUN = 6000

PAR_DEFINE_GRADIENT_THRESHOLD_HEATING = 0.5 # in °C/s, if the temperature gradient is above this threshold, it is likely that the burner is active
PAR_DEFINE_GRADIENT_THRESHOLD_COOLING = -0.5 # in °C/s, if the temperature gradient is below this threshold, it is likely that the burner is inactive   

# only relevant for the first sample, if there is no previous sample to compare the gradient with, the temperature itself can be used to determine the burner status, as a high temperature (e.g. above 125°C) is a strong indicator for an active burner
PAR_DEFINE_EXHAUST_TEMPERATURE_ON_THRESHOLD = 125.0 # in °C, if the temperature is above this threshold, it is likely that the burner is active

@dataclasses.dataclass
class exhaustTemperatureSample:
    id: int         # ID of the database entry
    time: int          # Unix Timestamp
    temperature: float
    processed: bool | None = None # flag if the sample has been processed for analysis

@dataclasses.dataclass
class exhaustTemperatureGradientSample:
    id: int         # ID of the database entry
    time: int          # Unix Timestamp
    gradient: float

@dataclasses.dataclass
class oilBurnerStatus:
    id: int            # ID of the database entry
    time: int          # start time of the status
    status: bool

@dataclasses.dataclass
class oilBurnerPulse:
    id: int        # ID of the database entry
    time: int      # Unix Timestamp (start of the status period)
    status: bool
    duration: int  # duration in seconds   

@dataclasses.dataclass
class oilBurnerStatusEvent:
    id: int        # ID of the database entry (same as the brennerStatus sample id)
    time: int      # Unix Timestamp of the status change
    status: bool   # new status after the change

@dataclasses.dataclass
class oilBurnerStatistics:
    gesamtdauerAktiv: int = 0
    gesamtdauerInaktiv: int = 0
    starts: int = 0
    pausen: int = 0
    mittlereDauerAktiv: float = 0.0
    mittlereDauerInaktiv: float = 0.0



oilBurnerStatisticsData: oilBurnerStatistics = oilBurnerStatistics()
oilBurnerStatusData: list[oilBurnerStatus] = []
exhaustTemperatureData: list[exhaustTemperatureSample] = []
oilBurnerPulseData: list[oilBurnerPulse] = []

def exhaustTemperatureAnalysis():

    if isNewExhaustSampleAvailable():
        print("New exhaust temperature sample available, processing...")
        processNewExhaustSamples()

    if isNewGradientSampleAvailable():
        print("New exhaust temperature gradient sample available, processing...")
        processNewGradientSamples()

    if isNewBurnerStatusSampleAvailable():
        print("New burner status sample available, processing...")
        processNewBurnerStatusSamples()


def processNewGradientSamples():
    samplesProcessed = 0
    while isNewGradientSampleAvailable():
        if samplesProcessed >= PAR_DEFINE_MAX_SAMPLES_PROCESSED_PER_RUN:
            print(f"Processed {samplesProcessed} gradient samples, reaching the maximum limit for this run.")
            break
        else:
            processGradientSample()
            samplesProcessed += 1

def processNewExhaustSamples():
    samplesProcessed = 0
    while isNewExhaustSampleAvailable():
        if samplesProcessed >= PAR_DEFINE_MAX_SAMPLES_PROCESSED_PER_RUN:
            print(f"Processed {samplesProcessed} temperatue samples, reaching the maximum limit for this run.")
            break
        else:
            proccessExhaustSample()
            samplesProcessed += 1


def processNewBurnerStatusSamples():
    samplesProcessed = 0
    while isNewBurnerStatusSampleAvailable():
        if samplesProcessed >= PAR_DEFINE_MAX_SAMPLES_PROCESSED_PER_RUN:
            print(f"Processed {samplesProcessed} burner status samples, reaching the maximum limit for this run.")
            break
        else:
            processNewBurnerStatusSample()
            samplesProcessed += 1
    

def processNewBurnerStatusSample():
    newSample = getUnprocessedBurnerStatusSample()

    if newSample.id == getFirstBurnerStatusSampleId():
        print("This is the first burner status sample, no previous sample to compare with, skipping processing for this sample...")
        markBurnerStatusAsProcessed(newSample.id)
    elif burnerStatusSampleExists(newSample.id-1):
        print("Previous burner status sample exists, processing new sample...")
        previousSample = getBurnerStatusSampleById(newSample.id-1)

        if previousSample.status == False and newSample.status == True:
            print("Burner status changed from inactive to active, inserting status event...")
            event = oilBurnerStatusEvent(id=newSample.id, time=newSample.time, status=True)
            insertBurnerStatusEvent(event)
            print("Inserted burner status event (ON) into the database.")
        elif previousSample.status == True and newSample.status == False:
            print("Burner status changed from active to inactive, inserting status event...")
            event = oilBurnerStatusEvent(id=newSample.id, time=newSample.time, status=False)
            insertBurnerStatusEvent(event)
            print("Inserted burner status event (OFF) into the database.")
        else:
            print(f"No burner status change detected at sample ID {newSample.id}, skipping event insertion.")

        markBurnerStatusAsProcessed(newSample.id)
        print(f"Burner status sample {newSample.id} marked as processed.")
    else:
        print(f"Previous burner status sample {newSample.id-1} not found, skipping processing for now.")

def processGradientSample():
    newSample = getUnprocessedGradientSample()

    print(f"Processing new exhaust temperature gradient sample with ID {newSample.id} and gradient {newSample.gradient}°C/s at time {datetime.datetime.fromtimestamp(newSample.time).strftime('%Y-%m-%d %H:%M:%S')}")

    # check if previous gradient sample exists for the analysis
    if newSample.id == getFirstGradientSampleId():
        # check if temperature is above 125°C, which indicates that the burner is likely active
        print("This is the first gradient sample, checking if the corresponding temperature sample indicates an active burner...")
        exhaustTemperature = getExhaustSampleById(newSample.id).temperature
        if exhaustTemperature > PAR_DEFINE_EXHAUST_TEMPERATURE_ON_THRESHOLD:
            print("Burner is likely active based on the temperature sample.")
            burnerStatus = True
        else:
            print("Burner is likely inactive based on the temperature sample.")
            burnerStatus = False
        
        oilBurnerStatusSample = oilBurnerStatus(id=newSample.id, time=newSample.time, status=burnerStatus)

        insertBurnerStatusSample(oilBurnerStatusSample)
        print("Inserted burner status sample into the database.")

        markBurnerStatusSampleAsProcessed(newSample.id)
        print(f"Gradient sample {newSample.id} marked as processed.")
    elif newSample.gradient > PAR_DEFINE_GRADIENT_THRESHOLD_HEATING:
        print("Burner is likely active based on the temperature gradient.")
        burnerStatus = True
        oilBurnerStatusSample = oilBurnerStatus(id=newSample.id, time=newSample.time, status=burnerStatus)
        insertBurnerStatusSample(oilBurnerStatusSample)
        print("Inserted burner status sample into the database.")

        markBurnerStatusSampleAsProcessed(newSample.id)
        print(f"Gradient sample {newSample.id} marked as processed.")
    elif newSample.gradient < PAR_DEFINE_GRADIENT_THRESHOLD_COOLING:
        print("Burner is likely inactive based on the temperature gradient.")
        burnerStatus = False
        oilBurnerStatusSample = oilBurnerStatus(id=newSample.id, time=newSample.time, status=burnerStatus)
        insertBurnerStatusSample(oilBurnerStatusSample)
        print("Inserted burner status sample into the database.")

        markBurnerStatusSampleAsProcessed(newSample.id)
        print(f"Gradient sample {newSample.id} marked as processed.")
    else:
        #try to read the element before and copy its status, as the gradient is not significant enough to determine a status change
        print("Temperature gradient is not significant enough to determine a status change, trying to copy the previous status if available...")
        previousGradientSample = getExhaustSampleById(newSample.id-1)

        if previousGradientSample is not None:
            previousStatusSample = getBurnerStatusSampleById(previousGradientSample.id)

            if previousStatusSample is not None:
                print("Previous status sample found, copying the status to the new sample.")
                oilBurnerStatusSample = oilBurnerStatus(id=newSample.id, time=newSample.time, status=previousStatusSample.status)
                insertBurnerStatusSample(oilBurnerStatusSample)
                print("Inserted burner status sample into the database.")

                markBurnerStatusSampleAsProcessed(newSample.id)
                print(f"Gradient sample {newSample.id} marked as processed.")
            else:
                print("No previous status sample found, skipping this gradient sample for now.")
        else:
            print("No previous gradient sample found, skipping this gradient sample for now.")
            


def proccessExhaustSample():
    newSample = getUnprocessedExhaustSample()

    print(f"Processing new exhaust temperature sample with ID {newSample.id} and temperature {newSample.temperature}°C at time {datetime.datetime.fromtimestamp(newSample.time).strftime('%Y-%m-%d %H:%M:%S')}")

    # check if the next sample exists for the gradient calculation
    if exhaustSampleExists(newSample.id+1):
        print("element and next element exist, processing sample...")
        nextSample = getExhaustSampleById(newSample.id+1)

        gradient = calculateTemperatureGradient(newSample, nextSample)
        gradientSample = exhaustTemperatureGradientSample(id=newSample.id, time=newSample.time, gradient=gradient)

        print(f"Calculated temperature gradient: {gradientSample.gradient:.2f} °C/s")

        insertGradientSample(gradientSample)
        print("Inserted temperature gradient sample into the database.")

        markExhaustSampleAsProcessed(newSample.id)
        print(f"Sample {newSample.id} marked as processed.")
    else:
        print("Next sample does not exist yet, skipping processing for this sample.")



def markExhaustSampleAsProcessed(sample_id: int):
    """ Marks the exhaust temperature sample with the given id as processed in the database. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE oelheizung.abgastemperatur
        SET processed = TRUE
        WHERE id = %s
    """, (sample_id,))

    conn.commit()
    cursor.close()
    conn.close()


def insertBurnerStatusSample(sample: oilBurnerStatus):
    """ Inserts an oil burner status sample into the brennerStatus table. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO oelheizung.brennerStatus (id, time, status)
        VALUES (%s, FROM_UNIXTIME(%s), %s)
    """, (sample.id, sample.time, sample.status))

    conn.commit()
    cursor.close()
    conn.close()


def markBurnerStatusAsProcessed(burner_status_id: int):
    """ Marks the burner status sample with the given id as processed in the brennerStatus table. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE oelheizung.brennerStatus
        SET processed = TRUE
        WHERE id = %s
    """, (burner_status_id,))

    conn.commit()
    cursor.close()
    conn.close()


def insertBurnerStatusEvent(event: oilBurnerStatusEvent):
    """ Inserts a burner status change event into the brennerStatusEvent table. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO oelheizung.brennerStatusEvent (id, time, status)
        VALUES (%s, FROM_UNIXTIME(%s), %s)
    """, (event.id, event.time, event.status))

    conn.commit()
    cursor.close()
    conn.close()


def markBurnerStatusSampleAsProcessed(gradient_sample_id: int):
    """ Marks the gradient sample with the given id as processed in the abgastemperaturGradient table. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE oelheizung.abgastemperaturGradient
        SET processed = TRUE
        WHERE id = %s
    """, (gradient_sample_id,))

    conn.commit()
    cursor.close()
    conn.close()


def insertGradientSample(gradientSample: exhaustTemperatureGradientSample):
    """ Inserts an exhaust temperature gradient sample into the abgastemperaturGradient table. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        INSERT IGNORE INTO oelheizung.abgastemperaturGradient (id, time, gradient)
        VALUES (%s, FROM_UNIXTIME(%s), %s)
    """, (gradientSample.id, gradientSample.time, gradientSample.gradient))

    conn.commit()
    cursor.close()
    conn.close()


def calculateTemperatureGradient(firstSample: exhaustTemperatureSample, secondSample: exhaustTemperatureSample) -> float:
    """Calculates the temperature gradient between two exhaust temperature samples."""
    timeDifference = secondSample.time - firstSample.time
    if timeDifference == 0:
        return 0.0
    temperatureDifference = secondSample.temperature - firstSample.temperature
    return temperatureDifference / timeDifference

def getExhaustSampleById(sample_id: int) -> exhaustTemperatureSample | None:
    """ This function reads the exhaust temperature sample with the given id from the database and returns it as an AbgasTemperatur object. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, UNIX_TIMESTAMP(time), temperatur, processed
        FROM oelheizung.abgastemperatur
        WHERE id = %s
    """, (sample_id,))

    row = cursor.fetchone()

    if row is not None:
        sample = exhaustTemperatureSample(id=row[0], time=row[1], temperature=row[2], processed=row[3])
    else:
        sample = None

    cursor.close()
    conn.close()

    return sample


def getBurnerStatusSampleById(sample_id: int) -> oilBurnerStatus | None:
    """ Reads the burner status sample with the given id from the brennerStatus table. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, UNIX_TIMESTAMP(time), status
        FROM oelheizung.brennerStatus
        WHERE id = %s
        LIMIT 1
    """, (sample_id,))

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row is not None:
        return oilBurnerStatus(id=row[0], time=row[1], status=bool(row[2]))
    return None


def getFirstBurnerStatusSampleId() -> int | None:
    """ Returns the id of the first (smallest id) burner status sample in the database, or None if the table is empty. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM oelheizung.brennerStatus
        ORDER BY id ASC
        LIMIT 1
    """)

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    return row[0] if row else None


def getFirstGradientSampleId() -> int | None:
    """ Returns the id of the first (smallest id) gradient sample in the database, or None if the table is empty. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM oelheizung.abgastemperaturGradient
        ORDER BY id ASC
        LIMIT 1
    """)

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    return row[0] if row else None


def getUnprocessedBurnerStatusSample() -> oilBurnerStatus | None:
    """ Reads the first unprocessed burner status sample from the brennerStatus table. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, UNIX_TIMESTAMP(time), status
        FROM oelheizung.brennerStatus
        WHERE processed IS NULL OR processed = FALSE
        ORDER BY time ASC
        LIMIT 1
    """)

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row is not None:
        return oilBurnerStatus(id=row[0], time=row[1], status=bool(row[2]))
    return None


def getUnprocessedGradientSample():
    """ This function reads the first element of the oelheizung.abgastemperaturGradient table which
    has a processed value of NULL and returns it as an exhaustTemperatureGradientSample object.
      After reading the sample, it sets the processed value to the current timestamp to mark it as processed. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, UNIX_TIMESTAMP(time), gradient
        FROM oelheizung.abgastemperaturGradient
        WHERE processed IS NULL OR processed = FALSE
        ORDER BY time ASC
        LIMIT 1
    """)

    row = cursor.fetchone()

    if row is not None:
        sample = exhaustTemperatureGradientSample(id=row[0], time=row[1], gradient=row[2])
    else:
        sample = None

    cursor.close()
    conn.close()

    return sample


def getUnprocessedExhaustSample():
    """ This function reads the first element of the oelheizung.abgastemperatur table which
    has a processed value of NULL and returns it as an AbgasTemperatur object.
      After reading the sample, it sets the processed value to the current timestamp to mark it as processed. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, UNIX_TIMESTAMP(time), temperatur
        FROM oelheizung.abgastemperatur
        WHERE processed IS NULL OR processed = FALSE
        ORDER BY time ASC
        LIMIT 1
    """)

    row = cursor.fetchone()

    if row is not None:
        sample = exhaustTemperatureSample(id=row[0], time=row[1], temperature=row[2])
    else:
        sample = None

    cursor.close()
    conn.close()

    return sample

def resetProcessedFlagForAllSamples():
    """ This function resets the processed flag for all samples in the database to NULL. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE oelheizung.abgastemperatur
        SET processed = NULL
    """)

    conn.commit()
    cursor.close()
    conn.close()

    print("Reset processed flag for all samples in the database.")


def markExhaustSampleAsProcessed(sample_id: int):
    """ Marks the exhaust temperature sample with the given id as processed in the database. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE oelheizung.abgastemperatur
        SET processed = TRUE
        WHERE id = %s
    """, (sample_id,))

    conn.commit()
    cursor.close()
    conn.close()


def burnerStatusSampleExists(sample_id: int) -> bool:
    """ Checks if a burner status sample with the given id exists in the brennerStatus table. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1
        FROM oelheizung.brennerStatus
        WHERE id = %s
        LIMIT 1
    """, (sample_id,))

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    return result is not None


def exhaustSampleExists(sample_id: int) -> bool:
    """ Checks if an exhaust temperature sample with the given id exists in the database. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1
        FROM oelheizung.abgastemperatur
        WHERE id = %s
        LIMIT 1
    """, (sample_id,))

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    return result is not None


def isNewExhaustSampleAvailable() -> bool:
    """
    Checks if a new exhaust temperature sample is available in the database
    by reading the first element which has a oelheizung.processed set to NULL.

    Returns:
        bool: True if at least one new exhaust temperature sample is available, False otherwise.

    Author
    -----
    Marcel Riebel
    """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.id
        FROM oelheizung.abgastemperatur a
        WHERE (a.processed IS NULL OR a.processed = FALSE)
          AND EXISTS (
              SELECT 1 FROM oelheizung.abgastemperatur b WHERE b.id = a.id + 1
          )
        LIMIT 1
    """)

    result = cursor.fetchone()
    new_samples_available = result is not None

    cursor.close()
    conn.close()

    return new_samples_available


def isNewGradientSampleAvailable() -> bool:
    """
    Checks if a new exhaust temperature gradient sample is available in the database
    by reading the first element which has a oelheizung.abgastemperaturGradient.processed set to NULL.

    Returns:
        bool: True if at least one new exhaust temperature gradient sample is available, False otherwise.

    Author
    -----
    Marcel Riebel
    """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1
        FROM oelheizung.abgastemperaturGradient
        WHERE processed IS NULL OR processed = FALSE
        LIMIT 1
    """)

    result = cursor.fetchone()
    new_samples_available = result is not None

    cursor.close()
    conn.close()

    return new_samples_available


def isNewBurnerStatusSampleAvailable() -> bool:
    """ Checks if a new burner status sample is available in the brennerStatus table that has not been processed yet. """
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1
        FROM oelheizung.brennerStatus
        WHERE processed IS NULL OR processed = FALSE
        LIMIT 1
    """)

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    return result is not None


def leseAbgasTemperatur():
    global AbgasTemperaturDaten
    AbgasTemperaturDaten.clear()

    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT UNIX_TIMESTAMP(time), temperatur
        FROM oelheizung.abgastemperatur
        WHERE time >= NOW() - INTERVAL 24 HOUR
        ORDER BY time ASC
    """)

    rows = cursor.fetchall()

    for ts, temperatur in rows:
        exhaustTemperatureData.append(exhaustTemperatureSample(time=ts, temperatur=temperatur))

    cursor.close()
    conn.close()


if __name__ == "__main__":
    exhaustTemperatureAnalysis()
