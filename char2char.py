# Char2Char
# Input: Sequence of letters
# Output: a sorted version of that sequence

import numpy as np
import time

# Dataset
# letters_source.txt:
#   The list of input letter sequences. Each sequence is its own line.
# letters_target.txt:
#   The list of target sequences we'll use in the training process.
source_path = 'data/letters_source.txt'
target_path = 'data/letters_target.txt'

source_sentences = open(source_path, 'r').read()
target_sentences = open(target_path, 'r').read()


def extract_character_vocab(data):
    special_words = ['<PAD>', '<UNK>', '<GO>',  '<EOS>']

    set_words = set([character for line in data.split('\n') for character in line])
    int_to_vocab = {word_i: word for word_i, word in enumerate(special_words + list(set_words))}
    vocab_to_int = {word: word_i for word_i, word in int_to_vocab.items()}

    return int_to_vocab, vocab_to_int

# Build int2letter and letter2int dicts
source_int_to_letter, source_letter_to_int = extract_character_vocab(source_sentences)
target_int_to_letter, target_letter_to_int = extract_character_vocab(target_sentences)

# Convert characters to ids
source_letter_ids = [[source_letter_to_int.get(letter, source_letter_to_int['<UNK>']) for letter in line] for line in source_sentences.split('\n')]
target_letter_ids = [[target_letter_to_int.get(letter, target_letter_to_int['<UNK>']) for letter in line] + [target_letter_to_int['<EOS>']] for line in target_sentences.split('\n')]

print("Example source sequence")
print(source_letter_ids[:3])
print("\n")
print("Example target sequence")
print(target_letter_ids[:3])

set_words = set([character for line in source_sentences.split('\n') for character in line])
int_to_vocab = {word_i: word for word_i, word in enumerate(list(set_words))}

print(set_words)
print(int_to_vocab)




######
# Embed the input data, construct our encoder,
# then pass the embedded data to the encoder.

def encoding_layer(input_data, rnn_size, num_layers,
                   source_sequence_length, source_vocab_size,
                   encoding_embedding_size):


    # 1. Encoder embedding (Maps a sequence of symbols to a sequence of embeddings)
    # tf.contrib.layers.embed_sequence( ids, vocab_size=None, embed_dim=None, unique=False, initializer=None,
    #                                   regularizer=None, trainable=True, scope=None, reuse=None
    enc_embed_input = tf.contrib.layers.embed_sequence(input_data, source_vocab_size, encoding_embedding_size)
                          #
    # 2. RNN cell
    def make_cell(rnn_size):
        enc_cell = tf.contrib.rnn.LSTMCell(rnn_size, initializer=tf.random_uniform_initializer(-0.1, 0.1, seed=2))
        return enc_cell

    enc_cell = tf.contrib.rnn.MultiRNNCell([make_cell(rnn_size) for _ in range(num_layers)])
    enc_output, enc_state = tf.nn.dynamic_rnn(enc_cell, enc_embed_input, sequence_length=source_sequence_length, dtype=tf.float32)
    return enc_output, enc_state



def decoding_layer(target_letter_to_int, decoding_embedding_size, num_layers, rnn_size,
                   target_sequence_length, max_target_sequence_length, enc_state, dec_input):
    # 1. Decoder Embedding
    target_vocab_size = len(target_letter_to_int)
    dec_embeddings = tf.Variable(tf.random_uniform([target_vocab_size, decoding_embedding_size]))
    dec_embed_input = tf.nn.embedding_lookup(dec_embeddings, dec_input)

    # 2. Construct the decoder cell
    def make_cell(rnn_size):
        dec_cell = tf.contrib.rnn.LSTMCell(rnn_size, initializer=tf.random_uniform_initializer(-0.1, 0.1, seed=2))
        return dec_cell

    dec_cell = tf.contrib.rnn.MultiRNNCell([make_cell(rnn_size) for _ in range(num_layers)])

    # 3. Dense layer to translate the decoder's output at each time
    # step into a choice from the target vocabulary
    output_layer = Dense(target_vocab_size,
                         kernel_initializer = tf.truncated_normal_initializer(mean = 0.0, stddev=0.1))


    # 4. Set up a training decoder and an inference decoder
    # Training Decoder
    with tf.variable_scope("decode"):

        # Helper for the training process. Used by BasicDecoder to read inputs.
        training_helper = tf.contrib.seq2seq.TrainingHelper(inputs=dec_embed_input,
                                                            sequence_length=target_sequence_length,
                                                            time_major=False)


        # Basic decoder
        training_decoder = tf.contrib.seq2seq.BasicDecoder(dec_cell,
                                                           training_helper,
                                                           enc_state,
                                                           output_layer)

        # Perform dynamic decoding using the decoder
        training_decoder_output = tf.contrib.seq2seq.dynamic_decode(training_decoder,
                                                                       impute_finished=True,
                                                                       maximum_iterations=max_target_sequence_length)[0]
    # 5. Inference Decoder
    # Reuses the same parameters trained by the training process
    with tf.variable_scope("decode", reuse=True):
        start_tokens = tf.tile(tf.constant([target_letter_to_int['<GO>']], dtype=tf.int32), [batch_size], name='start_tokens')

        # Helper for the inference process.
        inference_helper = tf.contrib.seq2seq.GreedyEmbeddingHelper(dec_embeddings,
                                                                start_tokens,
                                                                target_letter_to_int['<EOS>'])

        # Basic decoder
        inference_decoder = tf.contrib.seq2seq.BasicDecoder(dec_cell,
                                                        inference_helper,
                                                        enc_state,
                                                        output_layer)

        # Perform dynamic decoding using the decoder
        inference_decoder_output = tf.contrib.seq2seq.dynamic_decode(inference_decoder,
                                                            impute_finished=True,
                                                            maximum_iterations=max_target_sequence_length)[0]



    return training_decoder_output, inference_decoder_output


def seq2seq_model(input_data, targets, lr, target_sequence_length,
                  max_target_sequence_length, source_sequence_length,
                  source_vocab_size, target_vocab_size,
                  enc_embedding_size, dec_embedding_size,
                  rnn_size, num_layers):

    # Pass the input data through the encoder. We'll ignore the encoder output, but use the state
    _, enc_state = encoding_layer(input_data,
                                  rnn_size,
                                  num_layers,
                                  source_sequence_length,
                                  source_vocab_size,
                                  encoding_embedding_size)


    # Prepare the target sequences we'll feed to the decoder in training mode
    dec_input = process_decoder_input(targets, target_letter_to_int, batch_size)

    # Pass encoder state and decoder inputs to the decoders
    training_decoder_output, inference_decoder_output = decoding_layer(target_letter_to_int,
                                                                       decoding_embedding_size,
                                                                       num_layers,
                                                                       rnn_size,
                                                                       target_sequence_length,
                                                                       max_target_sequence_length,
                                                                       enc_state,
                                                                       dec_input)

    return training_decoder_output, inference_decoder_output




def get_batches(targets, sources, batch_size, source_pad_int, target_pad_int):
    """Batch targets, sources, and the lengths of their sentences together"""
    for batch_i in range(0, len(sources)//batch_size):
        start_i = batch_i * batch_size
        sources_batch = sources[start_i:start_i + batch_size]
        targets_batch = targets[start_i:start_i + batch_size]
        pad_sources_batch = np.array(pad_sentence_batch(sources_batch, source_pad_int))
        pad_targets_batch = np.array(pad_sentence_batch(targets_batch, target_pad_int))

        # Need the lengths for the _lengths parameters
        pad_targets_lengths = []
        for target in pad_targets_batch:
            pad_targets_lengths.append(len(target))

        pad_source_lengths = []
        for source in pad_sources_batch:
            pad_source_lengths.append(len(source))

        yield pad_targets_batch, pad_sources_batch, pad_targets_lengths, pad_source_lengths


epochs = 60
batch_size = 128
rnn_size = 50
num_layers = 2
encoding_embedding_size = 15
decoding_embedding_size = 15
learning_rate = 0.001

# Split data to training and validation sets
train_source = source_letter_ids[batch_size:]
train_target = target_letter_ids[batch_size:]
valid_source = source_letter_ids[:batch_size]
valid_target = target_letter_ids[:batch_size]
(valid_targets_batch, valid_sources_batch, valid_targets_lengths, valid_sources_lengths) = next(get_batches(valid_target, valid_source, batch_size,
                           source_letter_to_int['<PAD>'],
                           target_letter_to_int['<PAD>']))

display_step = 20 # Check training loss after every 20 batches

checkpoint = "best_model.ckpt"
with tf.Session(graph=train_graph) as sess:
    sess.run(tf.global_variables_initializer())

    for epoch_i in range(1, epochs+1):
        for batch_i, (targets_batch, sources_batch, targets_lengths, sources_lengths) in enumerate(
                get_batches(train_target, train_source, batch_size,
                           source_letter_to_int['<PAD>'],
                           target_letter_to_int['<PAD>'])):

            # Training step
            _, loss = sess.run(
                [train_op, cost],
                {input_data: sources_batch,
                 targets: targets_batch,
                 lr: learning_rate,
                 target_sequence_length: targets_lengths,
                 source_sequence_length: sources_lengths})

            # Debug message updating us on the status of the training
            if batch_i % display_step == 0 and batch_i > 0:

                # Calculate validation cost
                validation_loss = sess.run(
                [cost],
                {input_data: valid_sources_batch,
                 targets: valid_targets_batch,
                 lr: learning_rate,
                 target_sequence_length: valid_targets_lengths,
                 source_sequence_length: valid_sources_lengths})

                print('Epoch {:>3}/{} Batch {:>4}/{} - Loss: {:>6.3f}  - Validation loss: {:>6.3f}'
                      .format(epoch_i,
                              epochs,
                              batch_i,
                              len(train_source) // batch_size,
                              loss,
                              validation_loss[0]))



    # Save Model
    saver = tf.train.Saver()
    saver.save(sess, checkpoint)
    print('Model Trained and Saved')
Prediction
In [ ]:
def source_to_seq(text):
    '''Prepare the text for the model'''
    sequence_length = 7
    return [source_letter_to_int.get(word, source_letter_to_int['<UNK>']) for word in text]+ [source_letter_to_int['<PAD>']]*(sequence_length-len(text))
In [ ]:
input_sentence = 'hello'
text = source_to_seq(input_sentence)

checkpoint = "./best_model.ckpt"

loaded_graph = tf.Graph()
with tf.Session(graph=loaded_graph) as sess:
    # Load saved model
    loader = tf.train.import_meta_graph(checkpoint + '.meta')
    loader.restore(sess, checkpoint)

    input_data = loaded_graph.get_tensor_by_name('input:0')
    logits = loaded_graph.get_tensor_by_name('predictions:0')
    source_sequence_length = loaded_graph.get_tensor_by_name('source_sequence_length:0')
    target_sequence_length = loaded_graph.get_tensor_by_name('target_sequence_length:0')

    #Multiply by batch_size to match the model's input parameters
    answer_logits = sess.run(logits, {input_data: [text]*batch_size,
                                      target_sequence_length: [len(text)]*batch_size,
                                      source_sequence_length: [len(text)]*batch_size})[0]


pad = source_letter_to_int["<PAD>"]

print('Original Text:', input_sentence)

print('\nSource')
print('  Word Ids:    {}'.format([i for i in text]))
print('  Input Words: {}'.format(" ".join([source_int_to_letter[i] for i in text])))

print('\nTarget')
print('  Word Ids:       {}'.format([i for i in answer_logits if i != pad]))
print('  Response Words: {}'.format(" ".join([target_int_to_letter[i] for i in answer_logits if i != pad])))
