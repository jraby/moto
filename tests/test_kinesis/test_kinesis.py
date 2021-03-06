from __future__ import unicode_literals

import boto.kinesis
from boto.kinesis.exceptions import ResourceNotFoundException, InvalidArgumentException
import sure  # noqa

from moto import mock_kinesis


@mock_kinesis
def test_create_cluster():
    conn = boto.kinesis.connect_to_region("us-west-2")

    conn.create_stream("my_stream", 2)

    stream_response = conn.describe_stream("my_stream")

    stream = stream_response["StreamDescription"]
    stream["StreamName"].should.equal("my_stream")
    stream["HasMoreShards"].should.equal(False)
    stream["StreamARN"].should.equal("arn:aws:kinesis:us-west-2:123456789012:my_stream")
    stream["StreamStatus"].should.equal("ACTIVE")

    shards = stream['Shards']
    shards.should.have.length_of(2)


@mock_kinesis
def test_describe_non_existant_stream():
    conn = boto.kinesis.connect_to_region("us-east-1")
    conn.describe_stream.when.called_with("not-a-stream").should.throw(ResourceNotFoundException)


@mock_kinesis
def test_list_and_delete_stream():
    conn = boto.kinesis.connect_to_region("us-west-2")

    conn.create_stream("stream1", 1)
    conn.create_stream("stream2", 1)

    conn.list_streams()['StreamNames'].should.have.length_of(2)

    conn.delete_stream("stream2")

    conn.list_streams()['StreamNames'].should.have.length_of(1)

    # Delete invalid id
    conn.delete_stream.when.called_with("not-a-stream").should.throw(ResourceNotFoundException)


@mock_kinesis
def test_basic_shard_iterator():
    conn = boto.kinesis.connect_to_region("us-west-2")

    stream_name = "my_stream"
    conn.create_stream(stream_name, 1)

    response = conn.describe_stream(stream_name)
    shard_id = response['StreamDescription']['Shards'][0]['ShardId']

    response = conn.get_shard_iterator(stream_name, shard_id, 'TRIM_HORIZON')
    shard_iterator = response['ShardIterator']

    response = conn.get_records(shard_iterator)
    shard_iterator = response['NextShardIterator']
    response['Records'].should.equal([])


@mock_kinesis
def test_get_invalid_shard_iterator():
    conn = boto.kinesis.connect_to_region("us-west-2")

    stream_name = "my_stream"
    conn.create_stream(stream_name, 1)

    conn.get_shard_iterator.when.called_with(stream_name, "123", 'TRIM_HORIZON').should.throw(ResourceNotFoundException)


@mock_kinesis
def test_put_records():
    conn = boto.kinesis.connect_to_region("us-west-2")

    stream_name = "my_stream"
    conn.create_stream(stream_name, 1)

    data = "hello world"
    partition_key = "1234"
    conn.put_record(stream_name, data, partition_key)

    response = conn.describe_stream(stream_name)
    shard_id = response['StreamDescription']['Shards'][0]['ShardId']

    response = conn.get_shard_iterator(stream_name, shard_id, 'TRIM_HORIZON')
    shard_iterator = response['ShardIterator']

    response = conn.get_records(shard_iterator)
    shard_iterator = response['NextShardIterator']
    response['Records'].should.have.length_of(1)
    record = response['Records'][0]

    record["Data"].should.equal("hello world")
    record["PartitionKey"].should.equal("1234")
    record["SequenceNumber"].should.equal("1")


@mock_kinesis
def test_get_records_limit():
    conn = boto.kinesis.connect_to_region("us-west-2")

    stream_name = "my_stream"
    conn.create_stream(stream_name, 1)

    # Create some data
    data = "hello world"
    for index in range(5):
        conn.put_record(stream_name, data, index)

    # Get a shard iterator
    response = conn.describe_stream(stream_name)
    shard_id = response['StreamDescription']['Shards'][0]['ShardId']
    response = conn.get_shard_iterator(stream_name, shard_id, 'TRIM_HORIZON')
    shard_iterator = response['ShardIterator']

    # Retrieve only 3 records
    response = conn.get_records(shard_iterator, limit=3)
    response['Records'].should.have.length_of(3)

    # Then get the rest of the results
    next_shard_iterator = response['NextShardIterator']
    response = conn.get_records(next_shard_iterator)
    response['Records'].should.have.length_of(2)


@mock_kinesis
def test_get_records_at_sequence_number():
    # AT_SEQUENCE_NUMBER - Start reading exactly from the position denoted by a specific sequence number.
    conn = boto.kinesis.connect_to_region("us-west-2")
    stream_name = "my_stream"
    conn.create_stream(stream_name, 1)

    # Create some data
    for index in range(1, 5):
        conn.put_record(stream_name, str(index), index)

    # Get a shard iterator
    response = conn.describe_stream(stream_name)
    shard_id = response['StreamDescription']['Shards'][0]['ShardId']
    response = conn.get_shard_iterator(stream_name, shard_id, 'TRIM_HORIZON')
    shard_iterator = response['ShardIterator']

    # Get the second record
    response = conn.get_records(shard_iterator, limit=2)
    second_sequence_id = response['Records'][1]['SequenceNumber']

    # Then get a new iterator starting at that id
    response = conn.get_shard_iterator(stream_name, shard_id, 'AT_SEQUENCE_NUMBER', second_sequence_id)
    shard_iterator = response['ShardIterator']

    response = conn.get_records(shard_iterator)
    # And the first result returned should be the second item
    response['Records'][0]['SequenceNumber'].should.equal(second_sequence_id)
    response['Records'][0]['Data'].should.equal('2')


@mock_kinesis
def test_get_records_after_sequence_number():
    # AFTER_SEQUENCE_NUMBER - Start reading right after the position denoted by a specific sequence number.
    conn = boto.kinesis.connect_to_region("us-west-2")
    stream_name = "my_stream"
    conn.create_stream(stream_name, 1)

    # Create some data
    for index in range(1, 5):
        conn.put_record(stream_name, str(index), index)

    # Get a shard iterator
    response = conn.describe_stream(stream_name)
    shard_id = response['StreamDescription']['Shards'][0]['ShardId']
    response = conn.get_shard_iterator(stream_name, shard_id, 'TRIM_HORIZON')
    shard_iterator = response['ShardIterator']

    # Get the second record
    response = conn.get_records(shard_iterator, limit=2)
    second_sequence_id = response['Records'][1]['SequenceNumber']

    # Then get a new iterator starting after that id
    response = conn.get_shard_iterator(stream_name, shard_id, 'AFTER_SEQUENCE_NUMBER', second_sequence_id)
    shard_iterator = response['ShardIterator']

    response = conn.get_records(shard_iterator)
    # And the first result returned should be the third item
    response['Records'][0]['Data'].should.equal('3')


@mock_kinesis
def test_get_records_latest():
    # LATEST - Start reading just after the most recent record in the shard, so that you always read the most recent data in the shard.
    conn = boto.kinesis.connect_to_region("us-west-2")
    stream_name = "my_stream"
    conn.create_stream(stream_name, 1)

    # Create some data
    for index in range(1, 5):
        conn.put_record(stream_name, str(index), index)

    # Get a shard iterator
    response = conn.describe_stream(stream_name)
    shard_id = response['StreamDescription']['Shards'][0]['ShardId']
    response = conn.get_shard_iterator(stream_name, shard_id, 'TRIM_HORIZON')
    shard_iterator = response['ShardIterator']

    # Get the second record
    response = conn.get_records(shard_iterator, limit=2)
    second_sequence_id = response['Records'][1]['SequenceNumber']

    # Then get a new iterator starting after that id
    response = conn.get_shard_iterator(stream_name, shard_id, 'LATEST', second_sequence_id)
    shard_iterator = response['ShardIterator']

    # Write some more data
    conn.put_record(stream_name, "last_record", "last_record")

    response = conn.get_records(shard_iterator)
    # And the only result returned should be the new item
    response['Records'].should.have.length_of(1)
    response['Records'][0]['PartitionKey'].should.equal('last_record')
    response['Records'][0]['Data'].should.equal('last_record')


@mock_kinesis
def test_invalid_shard_iterator_type():
    conn = boto.kinesis.connect_to_region("us-west-2")
    stream_name = "my_stream"
    conn.create_stream(stream_name, 1)

    response = conn.describe_stream(stream_name)
    shard_id = response['StreamDescription']['Shards'][0]['ShardId']
    response = conn.get_shard_iterator.when.called_with(
        stream_name, shard_id, 'invalid-type').should.throw(InvalidArgumentException)
