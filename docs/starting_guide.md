Getting started
===============

It is strongly recommended that you should start working on your compilers coursework straight after finishing the lab exercises, to have the time to implement a good number of features. Don't worry if you haven't properly done lab 3 yet, as lab 2 is a great starting point for the coursework, and might be the best example of how to structure your solutions. Thinking about how to structure the AST is one of the more challenging parts of the coursework, so you can focus on that and add code generation in later once you have more experience. 

To get started, you are strongly recommend to get familiar with the code in the repository already, then think about how to handle an extremely simple program, such as:

```
int f() {
    return 5;
}
```
Think about what kind of information you need to capture here, and what sort of classes would be useful. You might even find drawing the AST by hand help you better understand what is really happening behind the scenes. Make sure to benefit from the provided skeleton code and use the online resources that we have linked.

Don't worry if you find it difficult to get started or feel a little overwhelmed at first, this is perfectly normal (it often takes over a week to even get the most basic program to compile). Once you have a good base, you will find it much easier (and hopefully enjoyable) to add lots more features - although you will face more challenges when you get to more advanced features involving memory management. If you get stuck, you can always post on Ed or ask the TAs in the lab sessions! Also don't worry if you can't get everything done, although it is theoretically possible to get full marks in this coursework, no one has ever accomplished this - there's just too much to implement. I strongly recommend you spend as much time as you can working on it, as the more you try the more you will learn and get out of this project (and in our unbiased opinion it is the most fun coursework you will do during your degree), but don't sacrifice all of your other modules to try and chase the 100% score.

Test cases
----------

Although we provide you with a pretty large set of tests, these do not cover all of the functionality you need to implement by any means, so make sure to write your own to make sure the features you are adding work properly, this will help make your compiler more robust and pass more of the unseen test cases. It will also make your project look more robust and thoughtful.

Plagiarism and AI use
---------------------

One final thing, please don't copy any existing solutions from previous years you find online. In previous years we had quite a few groups do this and unsurprisingly they were all caught (some of us have been checking this coursework for 5 years and have seen most of the solutions online), and although you are targeting a different ISA compared to some years ago, there is still a lot you can copy as code generation is just one (arguably easier) part of the coursework. It can be fine to look at these solutions to get ideas on how to make high-level decisions like AST structure, but make sure you actually write the code yourself. The same goes for using LLMs (a.k.a. AI chatbots like ChatGPT) -- if you want, use them to your advantage for debugging or prototyping, but be aware of blindly implementing a different compiler than you have been asked for or copying a solution that will get flagged for similarity with other solutions found online (as you know, ChatGPT simply learns from what is out there on the Internet). Remember that while it might look daunting at first, this coursework has been successfully completed by many generations of students before you, without access to ChatGPT and in significantly more difficult world circumstances, like lockdowns and pandemics.

Good luck!
