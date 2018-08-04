# -*- coding: utf-8 -*-
"""FR - EN Vanilla Encoder Decoder Machine Translation Model with LSTM.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/17mXoSQos_nGxyo7U2P8uM_reoKlVXxXa
"""

# importing required modules
import matplotlib.pyplot as plt, re
from google.colab import files
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.layers import Dense, Embedding, LSTM, RepeatVector, TimeDistributed
from keras.models import load_model, Sequential
from keras.preprocessing.sequence import pad_sequences
from keras.preprocessing.text import Tokenizer
from keras.utils import to_categorical
from numpy import argmax, array, empty, mean
from os import listdir, remove
from os.path import isfile, join
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split
from unicodedata import category, normalize

# removing the accents
def unicode_to_ascii(string):
    return ''.join(character for character in normalize('NFD', string) if category(character) != 'Mn')

# cleaning a sentence
def preprocess_sentence(line):
    # converting from unicode to ascii
    line = unicode_to_ascii(line.lower().strip())
    # creating a space between a word and the punctuation following it, and then collapsing multiple spaces
    line = re.sub(r'[" "]+', " ", re.sub(r"([!',-.0-9?])", r" \1 ", line))
    # replacing everything with space except a-z, A-Z, "!", "'", ",", "-", ".", "?"
    line = re.sub(r"[^a-zA-Z!',-.0-9?]+", " ", line).strip()
    return line

# creating line pairs in the format: [target, source]
def create_dataset(filename, size):
    # open the file as read only, read all text and split in lines
    pairs = open(filename, mode = 'rt', encoding='UTF-8').read().strip().split('\n')
    # reducing dataset, splitting into target - source pairs and cleaning
    line_pairs = [[preprocess_sentence(line) for line in pair.split('\t')] for pair in pairs[:size]]
    return array(line_pairs)

# finding maximum sentence length
def maximum_length(lines):
    return max(len(line.split()) for line in lines)

# creating a tokenizer to vectorize the sequence
def create_tokenizer(lines):
    tokenizer = Tokenizer(filters = '"#$%&()*+/:;<=>@[\]^_`{|}~')
    tokenizer.fit_on_texts(lines)
    return tokenizer

# encoding and padding the sequence to the maximum length
def encode_sequences(tokenizer, length, lines):
    # encoding sequence to integers
    X = tokenizer.texts_to_sequences(lines)
    # padding sequence with 0 values
    X = pad_sequences(X, maxlen = length, padding = 'post')
    return X

# performing one hot encode on target sequence
def encode_output(sequences, vocab_size):
    ylist = []
    for sequence in sequences:
        encoded = to_categorical(sequence, num_classes = vocab_size)
        ylist.append(encoded)
    y = array(ylist)
    y = y.reshape(sequences.shape[0], sequences.shape[1], vocab_size)
    return y

# loading training and testing data
def load_dataset(filename, size, shuffle_state = True, test_proportion = 0.2):
    # loading reduced modified line pairs
    combined_dataset = create_dataset(filename, size)
    # shuffling and splitting into training and testing subsets
    training_dataset, testing_dataset = train_test_split(combined_dataset, shuffle = shuffle_state, test_size = test_proportion)
    # preparing target tokenizer
    target_tokenizer = create_tokenizer(combined_dataset[:, 0])
    target_vocabulary_size = len(target_tokenizer.word_index) + 1
    maximum_target_length = maximum_length(combined_dataset[:, 0])
    # preparing source tokenizer
    source_tokenizer = create_tokenizer(combined_dataset[:, 1])
    source_vocabulary_size = len(source_tokenizer.word_index) + 1
    maximum_source_length = maximum_length(combined_dataset[:, 1])
    # preparing training data
    training_source = encode_sequences(source_tokenizer, maximum_source_length, training_dataset[:, 1])
    training_target = encode_sequences(target_tokenizer, maximum_target_length, training_dataset[:, 0])
    training_target = encode_output(training_target, target_vocabulary_size)
    # preparing testing data
    testing_source = encode_sequences(source_tokenizer, maximum_source_length, testing_dataset[:, 1])
    testing_target = encode_sequences(target_tokenizer, maximum_target_length, testing_dataset[:, 0])
    testing_target = encode_output(testing_target, target_vocabulary_size)
    # printing dataset information
    print('Source Vocabulary Size: %d' % source_vocabulary_size)
    print('Source Maximum Length: %d' % maximum_source_length)
    print('Target Vocabulary Size: %d' % target_vocabulary_size)
    print('Target Maximum Length: %d' % maximum_target_length)
    return combined_dataset, training_dataset, testing_dataset, training_source, training_target, testing_source, testing_target, source_vocabulary_size, target_vocabulary_size, maximum_source_length, maximum_target_length, source_tokenizer, target_tokenizer

# defining encoder decoder neural machine translation model
def define_model(source_vocabulary, target_vocabulary, source_timesteps, target_timesteps, n_units):
    model = Sequential()
    model.add(Embedding(source_vocabulary, n_units, input_length = source_timesteps, mask_zero = True))
    model.add(LSTM(n_units))
    model.add(RepeatVector(target_timesteps))
    model.add(LSTM(n_units, return_sequences = True))
    model.add(TimeDistributed(Dense(target_vocabulary, activation = 'softmax')))
    return model

# mapping an integer to a word
def word_for_id(integer, tokenizer):
    for word, index in tokenizer.word_index.items():
        if index == integer:
            return word
    return None

# generating target sequence given source sequence
def predict_sequence(model, target_tokenizer, source):
    prediction = model.predict(source, verbose = 0)[0]
    integers = [argmax(vector) for vector in prediction]
    target = []
    for i in integers:
        word = word_for_id(i, target_tokenizer)
        if word is None:
            break
        target.append(word)
    return ' '.join(target)
    
# evaluating a fitted model
def evaluate_model(model, target_tokenizer, testing_source, testing_target, testing_dataset):
    cosine_similarities = empty(len(testing_target))
    for i, source in enumerate(testing_source):
        # decoding predicted translations of encoded source text
        source = source.reshape((1, source.shape[0]))
        prediction = predict_sequence(model, target_tokenizer, source)
        target = testing_dataset[i][0]
        # calculating cosine similarity
        vectorisations = TfidfVectorizer().fit_transform([prediction, target])
        cosine_similarities[i] = cosine_similarity(vectorisations[0,], vectorisations[1,])
    # checking model performance
    metrics = model.evaluate(testing_source, testing_target, verbose = 0)
    # printing results
    print("Average Cosine Similarity: %.2f" % mean(cosine_similarities))
    print("Model %s: %.2f%%" % (model.metrics_names[1], metrics[1] * 100))

# translating source language text to target language text
def translate(source, model, source_tokenizer, target_tokenizer, maximum_source_length):
    encoded_source = encode_sequences(source_tokenizer, maximum_source_length, array([preprocess_sentence(source.strip())]))[0]
    decoded_translation = predict_sequence(model, target_tokenizer, encoded_source.reshape((1, encoded_source.shape[0])))
    return(decoded_translation)

# visualising a fitted model
def visualise_model(model, history, name, combined_dataset, source_tokenizer, target_tokenizer, maximum_source_length):
    print(model.summary())
    # plotting progress
    plt.plot(history.history['categorical_accuracy'])
    plt.plot(history.history['loss'])
    plt.plot(history.history['val_categorical_accuracy'])
    plt.plot(history.history['val_loss'])
    plt.title('Improvement during Training')
    plt.ylabel('Model Metrics')
    plt.xlabel('Number of Epochs Passed')
    plt.legend(['training accuracy', 'training loss', 'validation accuracy', 'validation loss'], loc = 'best')
    plt.savefig('%s_progress.png' % name)
    plt.close()
    for counter, language_pair in enumerate(combined_dataset):
        if counter % 2500 == 0:
            input_text = language_pair[1]
            expected_text = language_pair[0]
            output_text = translate(language_pair[1], model, source_tokenizer, target_tokenizer, maximum_source_length)
            print('source: [%s] \t target: [%s] \t result: [%s]' % (input_text, expected_text, output_text))

# removing all existing files
files_in_directory = [file for file in listdir('.') if isfile(join('.', file))]
for counter in files_in_directory:
    remove(counter)

# uploading file
uploaded = files.upload()

# loading reduced dataset
n_sentences = 35000
combined, train, test, trainX, trainY, testX, testY, vocabX, vocabY, sizeX, sizeY, tokenX, tokenY = load_dataset('fra.txt', n_sentences)

# defining model
fr_en_ed_model = define_model(vocabX, vocabY, sizeX, sizeY, 256)
fr_en_ed_model.compile(optimizer = 'adam', loss = 'categorical_crossentropy', metrics = ['categorical_accuracy'])

# setting callbacks to for the model during training
checkpoint = ModelCheckpoint(filepath = 'fr_en_ed_model.h5', save_best_only = True, verbose = 1)
earlystop = EarlyStopping(min_delta = 0.001, patience = 5, verbose = 1)

# fitting and visualising and evaluating the model
fr_en_ed_progress = fr_en_ed_model.fit(trainX, trainY, epochs = 100, batch_size = 64, validation_split = 0.25, callbacks = [checkpoint, earlystop], verbose = 0)
fr_en_ed_model = load_model('fr_en_ed_model.h5')
evaluate_model(fr_en_ed_model, tokenY, testX, testY, test)
visualise_model(fr_en_ed_model, fr_en_ed_progress, 'fr_en_ed', combined, tokenX, tokenY, sizeX)

# downloading files
files.download('fr_en_ed_progress.png')
files.download('fr_en_ed_model.h5')